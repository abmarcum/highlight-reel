variable "project_id" {
  description = "The ID of the GCP project"
  type        = string
}

variable "region" {
  description = "The default GCP region for resources"
  type        = string
  default     = "us-central1"
}

variable "env" {
  description = "The environment (e.g., dev, prod)"
  type        = string
  default     = "dev"
}

variable "iap_domain" {
  description = "The custom domain for the Global Load Balancer to provision an SSL certificate (required for IAP)."
  type        = string
  default     = "example.com"
}

variable "iap_client_id" {
  description = "OAuth 2.0 Client ID for IAP"
  type        = string
  default     = ""
}

variable "iap_client_secret" {
  description = "OAuth 2.0 Client Secret for IAP"
  type        = string
  sensitive   = true
  default     = ""
}

variable "gemini_api_key" {
  description = "The Gemini API Key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "slack_webhook_url" {
  description = "Slack notification webhook URL"
  type        = string
  sensitive   = true
}

variable "proxy_pass" {
  description = "Proxy authentication password"
  type        = string
  sensitive   = true
  default     = "NOT_SET"
}
