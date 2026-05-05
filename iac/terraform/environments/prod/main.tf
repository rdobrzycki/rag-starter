terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = ">= 5.0" }
  }
}

provider "aws" {
  region = var.aws_region
}

module "networking" {
  source                      = "../../modules/networking"
  name                        = var.name
  create_networking           = var.create_networking
  existing_vpc_id             = var.existing_vpc_id
  existing_public_subnet_ids  = var.existing_public_subnet_ids
  existing_private_subnet_ids = var.existing_private_subnet_ids
}

module "ssm_secrets" {
  source = "../../modules/ssm_secrets"
  name   = var.name
}

module "app_ingestion" {
  source         = "../../modules/app_ingestion"
  name           = var.name
  vpc_id         = module.networking.vpc_id
  aws_region     = var.aws_region
  git_commit_sha = var.git_commit_sha
}

module "app_api" {
  source                      = "../../modules/app_api"
  name                        = var.name
  aws_region                  = var.aws_region
  vpc_id                      = module.networking.vpc_id
  public_subnet_ids           = module.networking.public_subnet_ids
  private_subnet_ids          = module.networking.private_subnet_ids
  alb_security_group_id       = module.networking.alb_security_group_id
  ecs_tasks_security_group_id = module.networking.ecs_tasks_security_group_id
}

module "observability" {
  source               = "../../modules/observability"
  name                 = var.name
  aws_region           = var.aws_region
  cloudwatch_namespace = "RAG/Starter"
  ecs_cluster_name     = module.app_api.ecs_cluster_name
  ecs_service_name     = module.app_api.ecs_service_name
}

module "feedback_storage" {
  source      = "../../modules/feedback_storage"
  table_name  = "${var.name}-feedback"
  environment = "production"
}
