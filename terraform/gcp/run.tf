# ==========================================
# Video Renderer (Cloud Run Job)
# ==========================================
resource "google_cloud_run_v2_job" "video_renderer" {
  name     = "video-renderer-job"
  location = var.region

  template {
    template {
      max_retries = 3
      timeout     = "3600s" # 1 hour timeout for heavy ffmpeg rendering

      containers {
        image = "us-docker.pkg.dev/cloudrun/container/hello"

        resources {
          limits = {
            cpu    = "4"    # High CPU for ffmpeg
            memory = "16Gi" # High memory for complex 4k video processing
          }
        }

        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }

        env {
          name = "GEMINI_API_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.gemini_api_key.secret_id
              version = "latest"
            }
          }
        }
      }
      service_account = google_service_account.renderer.email
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].template[0].containers[0].image,
    ]
  }
}

# IAM rule allowing Eventarc/PubSub to execute the Job
resource "google_project_iam_member" "pubsub_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.audio_gen.email}"
}

# ==========================================
# Frontend UI (Cloud Run Service)
# ==========================================
resource "google_cloud_run_v2_service" "ui" {
  name     = "highlight-ui"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"

  template {
    containers {
      image = "us-docker.pkg.dev/cloudrun/container/hello"
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].containers[0].image,
    ]
  }
}

# Allow specific Google Groups or users to access the UI via IAP
# (If you want anyone who authenticates with a Google account to access it, use 'allAuthenticatedUsers')
# resource "google_cloud_run_v2_service_iam_member" "ui_iap_access" {
#   name     = google_cloud_run_v2_service.ui.name
#   location = google_cloud_run_v2_service.ui.location
#   project  = google_cloud_run_v2_service.ui.project
#   role     = "roles/run.invoker"
#   member   = "user:your-email@example.com"
# }
