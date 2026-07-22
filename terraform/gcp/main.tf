terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Enable required APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "storage.googleapis.com",
    "pubsub.googleapis.com",
    "cloudfunctions.googleapis.com",
    "run.googleapis.com",
    "bigquery.googleapis.com",
    "aiplatform.googleapis.com",
    "texttospeech.googleapis.com",
    "cloudbuild.googleapis.com",
    "videointelligence.googleapis.com"
  ])

  service            = each.key
  disable_on_destroy = false
}
