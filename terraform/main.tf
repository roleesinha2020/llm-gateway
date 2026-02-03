terraform {
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.0"
    }
  }
}

provider "kubernetes" {
  config_path = "~/.kube/config"
}

provider "helm" {
  kubernetes {
    config_path = "~/.kube/config"
  }
}

# Namespace isolates all gateway resources
resource "kubernetes_namespace" "llm_gateway" {
  metadata {
    name = "llm-gateway"
  }
}

# Non-secret configuration injected as env vars
resource "kubernetes_config_map" "gateway_config" {
  metadata {
    name      = "llm-gateway-config"
    namespace = kubernetes_namespace.llm_gateway.metadata[0].name
  }

  data = {
    REDIS_HOST         = "redis-service"
    POSTGRES_HOST      = "postgres-service"
    API_V1_STR         = "/api/v1"
    DEFAULT_RATE_LIMIT = "100"
    CACHE_TTL          = "3600"
    LOG_LEVEL          = "INFO"
  }
}

# Sensitive values — passed via variables, never in plain text
resource "kubernetes_secret" "gateway_secrets" {
  metadata {
    name      = "llm-gateway-secrets"
    namespace = kubernetes_namespace.llm_gateway.metadata[0].name
  }

  data = {
    OPENAI_API_KEY    = var.openai_api_key
    ANTHROPIC_API_KEY = var.anthropic_api_key
    SECRET_KEY        = var.secret_key
    POSTGRES_PASSWORD = var.postgres_password
  }
}

# Gateway: 3 replicas with health probes and resource limits
resource "kubernetes_deployment" "gateway" {
  metadata {
    name      = "llm-gateway"
    namespace = kubernetes_namespace.llm_gateway.metadata[0].name
  }

  spec {
    replicas = 3

    selector {
      match_labels = {
        app = "llm-gateway"
      }
    }

    template {
      metadata {
        labels = {
          app = "llm-gateway"
        }
      }

      spec {
        container {
          name  = "gateway"
          image = var.gateway_image

          port {
            container_port = 8000
          }

          env_from {
            config_map_ref {
              name = kubernetes_config_map.gateway_config.metadata[0].name
            }
          }

          env_from {
            secret_ref {
              name = kubernetes_secret.gateway_secrets.metadata[0].name
            }
          }

          resources {
            requests = {
              memory = "256Mi"
              cpu    = "250m"
            }
            limits = {
              memory = "512Mi"
              cpu    = "500m"
            }
          }

          liveness_probe {
            http_get {
              path = "/health"
              port = 8000
            }
            initial_delay_seconds = 30
            period_seconds        = 10
          }

          readiness_probe {
            http_get {
              path = "/health"
              port = 8000
            }
            initial_delay_seconds = 5
            period_seconds        = 5
          }
        }
      }
    }
  }
}

# LoadBalancer service exposes the gateway externally
resource "kubernetes_service" "gateway" {
  metadata {
    name      = "llm-gateway-service"
    namespace = kubernetes_namespace.llm_gateway.metadata[0].name
  }

  spec {
    selector = {
      app = "llm-gateway"
    }

    port {
      port        = 80
      target_port = 8000
    }

    type = "LoadBalancer"
  }
}

output "gateway_endpoint" {
  description = "External IP of the gateway LoadBalancer"
  value       = kubernetes_service.gateway.status[0].load_balancer[0].ingress[0].ip
}
