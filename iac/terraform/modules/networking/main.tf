data "aws_availability_zones" "available" {
  state = "available"
}

# Data sources for reusing existing resources
data "aws_vpc" "existing" {
  count = var.create_networking ? 0 : 1
  id    = var.existing_vpc_id
}

data "aws_subnet" "existing_public" {
  count = var.create_networking ? 0 : length(var.existing_public_subnet_ids)
  id    = var.existing_public_subnet_ids[count.index]
}

data "aws_subnet" "existing_private" {
  count = var.create_networking ? 0 : length(var.existing_private_subnet_ids)
  id    = var.existing_private_subnet_ids[count.index]
}

# Validate existing resources when reusing
locals {
  vpc_id               = var.create_networking ? aws_vpc.main[0].id : data.aws_vpc.existing[0].id
  public_subnet_ids    = var.create_networking ? aws_subnet.public[*].id : data.aws_subnet.existing_public[*].id
  private_subnet_ids   = var.create_networking ? aws_subnet.private[*].id : data.aws_subnet.existing_private[*].id
  private_subnet_cidrs = var.create_networking ? aws_subnet.private[*].cidr_block : data.aws_subnet.existing_private[*].cidr_block
}

# VPC
resource "aws_vpc" "main" {
  count                = var.create_networking ? 1 : 0
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.name}-vpc"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  count  = var.create_networking ? 1 : 0
  vpc_id = aws_vpc.main[0].id

  tags = {
    Name = "${var.name}-igw"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Public Subnets
resource "aws_subnet" "public" {
  count                   = var.create_networking ? 2 : 0
  vpc_id                  = aws_vpc.main[0].id
  cidr_block              = "10.0.${count.index + 1}.0/24"
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.name}-public-subnet-${count.index + 1}"
  }
}

# Private Subnets
resource "aws_subnet" "private" {
  count             = var.create_networking ? 2 : 0
  vpc_id            = aws_vpc.main[0].id
  cidr_block        = "10.0.${count.index + 11}.0/24"
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name = "${var.name}-private-subnet-${count.index + 1}"
  }
}

# Elastic IPs for NAT Gateways
resource "aws_eip" "nat" {
  count  = var.create_networking ? 2 : 0
  domain = "vpc"

  tags = {
    Name = "${var.name}-nat-eip-${count.index + 1}"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# NAT Gateways
resource "aws_nat_gateway" "main" {
  count         = var.create_networking ? 2 : 0
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  tags = {
    Name = "${var.name}-nat-${count.index + 1}"
  }

  depends_on = [aws_internet_gateway.main]

  lifecycle {
    create_before_destroy = false
  }
}

# Public Route Table
resource "aws_route_table" "public" {
  count  = var.create_networking ? 1 : 0
  vpc_id = aws_vpc.main[0].id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main[0].id
  }

  tags = {
    Name = "${var.name}-public-rt"
  }
}

# Public Route Table Associations
resource "aws_route_table_association" "public" {
  count          = var.create_networking ? 2 : 0
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public[0].id
}

# Private Route Tables
resource "aws_route_table" "private" {
  count  = var.create_networking ? 2 : 0
  vpc_id = aws_vpc.main[0].id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main[count.index].id
  }

  tags = {
    Name = "${var.name}-private-rt-${count.index + 1}"
  }
}

# Private Route Table Associations
resource "aws_route_table_association" "private" {
  count          = var.create_networking ? 2 : 0
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

# Security Group for ALB (API)
resource "aws_security_group" "alb" {
  name        = "${var.name}-alb-sg"
  description = "Security group for ALB"
  vpc_id      = local.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["64.98.116.72/32"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["64.98.116.72/32"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.name}-alb-sg"
  }
}

# Security Group for ECS Tasks
resource "aws_security_group" "ecs_tasks" {
  name        = "${var.name}-ecs-tasks-sg"
  description = "Security group for ECS tasks"
  vpc_id      = local.vpc_id

  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  # Allow traffic from private subnets (internal ALB lives in private subnets).
  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = local.private_subnet_cidrs
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.name}-ecs-tasks-sg"
  }
}

# Security Group for Lambda
resource "aws_security_group" "lambda" {
  name        = "${var.name}-lambda-sg"
  description = "Security group for Lambda functions"
  vpc_id      = local.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.name}-lambda-sg"
  }
}
