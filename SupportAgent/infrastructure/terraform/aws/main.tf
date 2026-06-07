terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# EKS Cluster
module "eks" {
  source = "./modules/eks"

  cluster_name    = var.cluster_name
  cluster_version = var.kubernetes_version
  region          = var.aws_region

  vpc_cidr = var.vpc_cidr

  node_groups = {
    general = {
      desired_size = var.node_group_desired_size
      min_size     = var.node_group_min_size
      max_size     = var.node_group_max_size
      instance_types = ["t3.xlarge"]
      disk_size    = 50
      labels = {
        role = "general"
      }
    }
  }

  tags = var.tags
}

# RDS PostgreSQL
module "rds" {
  source = "./modules/rds"

  identifier           = var.database_name
  engine               = "postgres"
  engine_version       = "16.1"
  instance_class       = var.db_instance_class
  allocated_storage    = var.db_allocated_storage
  storage_encrypted    = true
  backup_retention     = 30
  multi_az             = var.db_multi_az

  db_name  = "aiops_db"
  username = "aiops"
  password = var.db_password

  vpc_security_group_ids = [module.eks.rds_security_group_id]
  db_subnet_group_name   = module.eks.db_subnet_group_name

  tags = var.tags
}

# ElastiCache Redis
module "redis" {
  source = "./modules/elasticache"

  cluster_id           = var.cache_cluster_name
  engine               = "redis"
  engine_version       = "7.0"
  node_type            = var.cache_node_type
  num_cache_nodes      = 3
  automatic_failover   = true
  at_rest_encryption   = true
  transit_encryption   = true

  security_group_ids = [module.eks.redis_security_group_id]
  subnet_group_name  = module.eks.cache_subnet_group_name

  tags = var.tags
}

# S3 for ML models and artifacts
module "s3" {
  source = "./modules/s3"

  bucket_name = var.s3_bucket_name
  versioning  = true
  encryption  = true

  lifecycle_rules = [
    {
      prefix  = "models/"
      days    = 90
      storage_class = "STANDARD_IA"
    }
  ]

  tags = var.tags
}

# CloudWatch for Monitoring
module "monitoring" {
  source = "./modules/monitoring"

  cluster_name = var.cluster_name
  log_group_name = "/aws/eks/${var.cluster_name}"
  retention_days = 30

  tags = var.tags
}

# Output values
output "eks_cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "eks_cluster_name" {
  value = module.eks.cluster_name
}

output "rds_endpoint" {
  value = module.rds.endpoint
}

output "redis_endpoint" {
  value = module.redis.endpoint
}

output "s3_bucket_name" {
  value = module.s3.bucket_name
}
