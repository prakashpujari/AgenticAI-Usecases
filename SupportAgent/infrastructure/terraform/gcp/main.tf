terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

# GKE Cluster
module "gke" {
  source = "./modules/gke"

  cluster_name    = var.cluster_name
  region          = var.gcp_region
  kubernetes_version = var.kubernetes_version

  network_name = var.network_name
  subnet_name  = var.subnet_name

  node_pool = {
    name           = "default-pool"
    node_count     = var.node_count
    machine_type   = "n2-standard-4"
    disk_size_gb   = 100
    preemptible    = var.preemptible_nodes
  }

  labels = var.labels
}

# Cloud SQL PostgreSQL
module "cloudsql" {
  source = "./modules/cloudsql"

  instance_name       = var.database_name
  database_version    = "POSTGRES_16"
  tier                = var.db_tier
  availability_type   = var.db_availability_type
  backup_enabled      = true
  backup_location     = var.gcp_region

  database_name = "aiops_db"
  user_name     = "aiops"
  user_password = var.db_password

  network_id = var.network_id

  labels = var.labels
}

# Cloud Memorystore Redis
module "redis" {
  source = "./modules/redis"

  instance_id         = var.cache_instance_name
  tier                = "standard"
  memory_size_gb      = 5
  region              = var.gcp_region
  redis_version       = "7.0"
  display_name        = "AIOps Redis Cache"
  authorized_network  = var.network_name

  labels = var.labels
}

# Cloud Storage for ML models
module "gcs" {
  source = "./modules/gcs"

  bucket_name = var.storage_bucket_name
  location    = var.gcp_region
  versioning  = true
  uniform_bucket_level_access = true

  lifecycle_rules = [
    {
      action          = "SetStorageClass"
      storage_classes = ["NEARLINE"]
      age_days        = 90
    }
  ]

  labels = var.labels
}

# Monitoring
module "monitoring" {
  source = "./modules/monitoring"

  project_id = var.gcp_project_id
  cluster_name = var.cluster_name

  alert_policies = [
    {
      display_name = "High CPU usage"
      threshold    = 0.8
      metric_type  = "compute.googleapis.com/instance/cpu/utilization"
    }
  ]

  labels = var.labels
}

# Output values
output "gke_cluster_endpoint" {
  value = module.gke.endpoint
}

output "gke_cluster_name" {
  value = module.gke.cluster_name
}

output "cloudsql_instance_connection_name" {
  value = module.cloudsql.instance_connection_name
}

output "redis_host" {
  value = module.redis.host
}

output "gcs_bucket_name" {
  value = module.gcs.bucket_name
}
