resource "google_storage_bucket" "raw_videos" {
  name                        = "${var.project_id}-raw-videos"
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true

  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD", "PUT", "POST", "DELETE"]
    response_header = ["*"]
    max_age_seconds = 3600
  }

  lifecycle_rule {
    condition {
      age = 7
    }
    action {
      type = "Delete"
    }
  }
}

resource "google_storage_bucket" "processed_highlights" {
  name                        = "${var.project_id}-processed-highlights"
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true
}

resource "google_storage_bucket" "temp_processing" {
  name                        = "${var.project_id}-temp-processing"
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 7
    }
    action {
      type = "Delete"
    }
  }
}
