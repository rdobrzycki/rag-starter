variable "name" {
  type = string
}

variable "vpc_id" {
  type    = string
  default = null
}

variable "aws_region" {
  type    = string
  default = "us-east-2"
}

variable "git_commit_sha" {
  type        = string
  description = "Git commit SHA for tracking deployed code version"
  default     = "unknown"
}
