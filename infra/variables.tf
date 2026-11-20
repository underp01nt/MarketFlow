variable "aws_region" {
  type        = string
  default     = "us-east-1"
}

# range of IP addresses for our VPC
variable "vpc_cidr" {
  type        = string
  default     = "10.0.0.0/16"
}



#  Secrets/self declarable
variable "webull_secret_name" {
  type        = string
  default     = "marketflow/webull"
}

variable "webull_app_key" {
  type        = string
  sensitive   = true
}

variable "webull_app_secret" {
  type        = string
  sensitive   = true
}

variable "s3_bucket_name" {
  type        = string
}


#  ECR/S related
variable "ecr_repository_name" {
  description = "ECR repo for the poller image"
  type        = string
  default     = "marketflow-poller"
}

variable "image_tag" {
  type        = string
  default     = "latest"
}

variable "ecs_cluster_name" {
  description = "ECS cluster name"
  type        = string
  default     = "marketflow-cluster"
}

variable "task_definition_family" {
  description = "ECS task definition family"
  type        = string
  default     = "marketflow-poller"
}



#  CloudWatch 
variable "log_group_name" {
  description = "CloudWatch log group name"
  type        = string
  default     = "/ecs/marketflow-poller"
}
