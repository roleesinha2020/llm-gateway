variable "openai_api_key" {
  description = "OpenAI API Key"
  type        = string
  sensitive   = true
}

variable "anthropic_api_key" {
  description = "Anthropic API Key"
  type        = string
  sensitive   = true
}

variable "secret_key" {
  description = "Application Secret Key"
  type        = string
  sensitive   = true
}

variable "postgres_password" {
  description = "PostgreSQL Password"
  type        = string
  sensitive   = true
}

variable "gateway_image" {
  description = "Docker image for LLM Gateway"
  type        = string
  default     = "llm-gateway:latest"
}
