variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "cluster_name" {
  description = "EKS cluster name"
  type        = string
  default     = "aiops-cluster"
}

variable "kubernetes_version" {
  description = "Kubernetes version"
  type        = string
  default     = "1.28"
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "node_group_desired_size" {
  description = "EKS node group desired size"
  type        = number
  default     = 3
}

variable "node_group_min_size" {
  description = "EKS node group minimum size"
  type        = number
  default     = 1
}

variable "node_group_max_size" {
  description = "EKS node group maximum size"
  type        = number
  default     = 10
}

variable "database_name" {
  description = "RDS database name"
  type        = string
  default     = "aiops-db"
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.medium"
}

variable "db_allocated_storage" {
  description = "RDS allocated storage in GB"
  type        = number
  default     = 100
}

variable "db_multi_az" {
  description = "RDS multi-AZ deployment"
  type        = bool
  default     = true
}

variable "db_password" {
  description = "RDS database password"
  type        = string
  sensitive   = true
}

variable "cache_cluster_name" {
  description = "ElastiCache cluster name"
  type        = string
  default     = "aiops-cache"
}

variable "cache_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.medium"
}

variable "s3_bucket_name" {
  description = "S3 bucket name for ML models"
  type        = string
}

variable "tags" {
  description = "Common tags"
  type        = map(string)
  default = {
    Project     = "AIOps"
    Environment = "production"
    ManagedBy   = "Terraform"
  }
}
