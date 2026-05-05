variable "name" {
  type = string
}

variable "create_networking" {
  description = "Whether to create new networking resources or reuse existing ones"
  type        = bool
  default     = true
}

variable "existing_vpc_id" {
  description = "Existing VPC ID to reuse (required when create_networking=false)"
  type        = string
  default     = ""
}

variable "existing_public_subnet_ids" {
  description = "List of existing public subnet IDs to reuse (required when create_networking=false)"
  type        = list(string)
  default     = []
}

variable "existing_private_subnet_ids" {
  description = "List of existing private subnet IDs to reuse (required when create_networking=false)"
  type        = list(string)
  default     = []
}
