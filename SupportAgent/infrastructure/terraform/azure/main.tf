terraform {
  required_version = ">= 1.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.azure_subscription_id
}

# Resource Group
resource "azurerm_resource_group" "aiops" {
  name     = var.resource_group_name
  location = var.azure_region
}

# AKS Cluster
module "aks" {
  source = "./modules/aks"

  resource_group_name = azurerm_resource_group.aiops.name
  location            = azurerm_resource_group.aiops.location

  cluster_name       = var.cluster_name
  kubernetes_version = var.kubernetes_version

  node_pool = {
    name           = "default"
    node_count     = var.node_count
    vm_size        = "Standard_D4s_v3"
    os_disk_size_gb = 128
  }

  network_plugin = "azure"
  service_cidr   = var.service_cidr
  dns_service_ip = var.dns_service_ip

  tags = var.tags
}

# Azure Database for PostgreSQL
module "postgresql" {
  source = "./modules/postgresql"

  resource_group_name = azurerm_resource_group.aiops.name
  location            = azurerm_resource_group.aiops.location

  server_name             = var.database_name
  sku_name                = var.db_sku_name
  storage_mb              = var.db_storage_mb
  backup_retention_days   = 30
  geo_redundant_backup    = var.db_geo_redundant

  database_name = "aiops_db"
  admin_username = "aiops"
  admin_password = var.db_password

  tags = var.tags
}

# Azure Cache for Redis
module "redis" {
  source = "./modules/redis"

  resource_group_name = azurerm_resource_group.aiops.name
  location            = azurerm_resource_group.aiops.location

  name                = var.cache_name
  capacity            = 1
  family              = "P"
  sku_name            = "Premium"
  enable_non_ssl_port = false
  minimum_tls_version = "1.2"

  zones = ["1", "2"]

  tags = var.tags
}

# Storage Account for ML models
module "storage" {
  source = "./modules/storage"

  resource_group_name = azurerm_resource_group.aiops.name
  location            = azurerm_resource_group.aiops.location

  storage_account_name = var.storage_account_name
  account_tier         = "Standard"
  account_replication_type = "GRS"

  containers = [
    {
      name = "models"
      access_type = "private"
    },
    {
      name = "artifacts"
      access_type = "private"
    }
  ]

  tags = var.tags
}

# Application Insights for Monitoring
module "monitoring" {
  source = "./modules/monitoring"

  resource_group_name = azurerm_resource_group.aiops.name
  location            = azurerm_resource_group.aiops.location

  application_insights_name = var.app_insights_name
  application_type          = "web"
  retention_in_days         = 30

  tags = var.tags
}

# Output values
output "aks_kube_config" {
  value       = module.aks.kube_config_raw
  sensitive   = true
}

output "aks_cluster_name" {
  value = module.aks.cluster_name
}

output "postgresql_fqdn" {
  value = module.postgresql.fqdn
}

output "redis_hostname" {
  value = module.redis.hostname
}

output "storage_account_name" {
  value = module.storage.storage_account_name
}

output "app_insights_instrumentation_key" {
  value     = module.monitoring.instrumentation_key
  sensitive = true
}
