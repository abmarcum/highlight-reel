# Bucket for function source code
resource "google_storage_bucket" "function_source" {
  name                        = "${var.project_id}-function-source"
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true
}

# ==========================================
# Job Initiator Function (GCS Trigger)
# ==========================================
data "archive_file" "job_initiator_source" {
  type        = "zip"
  source_dir  = "${path.module}/../../backend/initiator"
  output_path = "${path.module}/job_initiator.zip"
}

resource "google_storage_bucket_object" "job_initiator_zip" {
  name   = "job_initiator-${data.archive_file.job_initiator_source.output_md5}.zip"
  bucket = google_storage_bucket.function_source.name
  source = data.archive_file.job_initiator_source.output_path
}

resource "google_cloudfunctions2_function" "job_initiator" {
  name        = "job-initiator"
  location    = var.region
  description = "Job initiator function triggered by GCS"

  build_config {
    runtime     = "python312"
    entry_point = "process_job"
    source {
      storage_source {
        bucket = google_storage_bucket.function_source.name
        object = google_storage_bucket_object.job_initiator_zip.name
      }
    }
  }

  service_config {
    max_instance_count    = 5
    available_memory      = "256M"
    timeout_seconds       = 60
    service_account_email = google_service_account.job_initiator.email
    environment_variables = {
      PROJECT_ID = var.project_id
    }
    secret_environment_variables {
      key        = "PROXY_PASS"
      project_id = var.project_id
      secret     = google_secret_manager_secret.proxy_pass.secret_id
      version    = "latest"
    }
  }

  event_trigger {
    trigger_region        = var.region
    event_type            = "google.cloud.storage.object.v1.finalized"
    retry_policy          = "RETRY_POLICY_DO_NOT_RETRY"
    service_account_email = google_service_account.job_initiator.email
    event_filters {
      attribute = "bucket"
      value     = google_storage_bucket.raw_videos.name
    }
  }

  depends_on = [
    google_project_iam_member.gcs_pubsub_publisher
  ]
}

# ==========================================
# Video Analyzer Function (Pub/Sub Trigger)
# ==========================================
data "archive_file" "video_analyzer_source" {
  type        = "zip"
  source_dir  = "${path.module}/../../backend/analyzer"
  output_path = "${path.module}/video_analyzer.zip"
}

resource "google_storage_bucket_object" "video_analyzer_zip" {
  name   = "video_analyzer-${data.archive_file.video_analyzer_source.output_md5}.zip"
  bucket = google_storage_bucket.function_source.name
  source = data.archive_file.video_analyzer_source.output_path
}

resource "google_cloudfunctions2_function" "video_analyzer" {
  name        = "video-analyzer"
  location    = var.region
  description = "Video analyzer function triggered by Pub/Sub"

  build_config {
    runtime     = "python312"
    entry_point = "analyze_video"
    source {
      storage_source {
        bucket = google_storage_bucket.function_source.name
        object = google_storage_bucket_object.video_analyzer_zip.name
      }
    }
  }

  service_config {
    max_instance_count    = 5
    available_memory      = "16G"
    available_cpu         = "4"
    timeout_seconds       = 3600
    service_account_email = google_service_account.video_analyzer.email
    environment_variables = {
      PROJECT_ID = var.project_id
    }
    secret_environment_variables {
      key        = "GEMINI_API_KEY"
      project_id = var.project_id
      secret     = google_secret_manager_secret.gemini_api_key.secret_id
      version    = "latest"
    }
  }

  event_trigger {
    trigger_region        = var.region
    event_type            = "google.cloud.pubsub.topic.v1.messagePublished"
    retry_policy          = "RETRY_POLICY_DO_NOT_RETRY"
    service_account_email = google_service_account.video_analyzer.email
    pubsub_topic          = google_pubsub_topic.topics["analyze-video"].id
  }
}

# ==========================================
# Audio Gen Function (Pub/Sub Trigger)
# ==========================================
data "archive_file" "audio_gen_source" {
  type        = "zip"
  source_dir  = "${path.module}/../../backend/audio_gen"
  output_path = "${path.module}/audio_gen.zip"
}

resource "google_storage_bucket_object" "audio_gen_zip" {
  name   = "audio_gen-${data.archive_file.audio_gen_source.output_md5}.zip"
  bucket = google_storage_bucket.function_source.name
  source = data.archive_file.audio_gen_source.output_path
}

resource "google_cloudfunctions2_function" "audio_gen" {
  name        = "audio-gen"
  location    = var.region
  description = "Audio generation function triggered by Pub/Sub"

  build_config {
    runtime     = "python312"
    entry_point = "generate_audio"
    source {
      storage_source {
        bucket = google_storage_bucket.function_source.name
        object = google_storage_bucket_object.audio_gen_zip.name
      }
    }
  }

  service_config {
    max_instance_count    = 5
    available_memory      = "256M"
    timeout_seconds       = 60
    service_account_email = google_service_account.audio_gen.email
    environment_variables = {
      PROJECT_ID    = var.project_id
      OUTPUT_BUCKET = "${var.project_id}-processed-highlights"
    }
  }

  event_trigger {
    trigger_region        = var.region
    event_type            = "google.cloud.pubsub.topic.v1.messagePublished"
    retry_policy          = "RETRY_POLICY_DO_NOT_RETRY"
    service_account_email = google_service_account.audio_gen.email
    pubsub_topic          = google_pubsub_topic.topics["generate-audio"].id
  }
}

# ==========================================
# Publisher Function (Pub/Sub Trigger)
# ==========================================
data "archive_file" "publisher_source" {
  type        = "zip"
  source_dir  = "${path.module}/../../backend/publisher"
  output_path = "${path.module}/publisher.zip"
}

resource "google_storage_bucket_object" "publisher_zip" {
  name   = "publisher-${data.archive_file.publisher_source.output_md5}.zip"
  bucket = google_storage_bucket.function_source.name
  source = data.archive_file.publisher_source.output_path
}

resource "google_cloudfunctions2_function" "publisher" {
  name        = "job-publisher"
  location    = var.region
  description = "Publisher function triggered by Pub/Sub"

  build_config {
    runtime     = "python312"
    entry_point = "publish_video"
    source {
      storage_source {
        bucket = google_storage_bucket.function_source.name
        object = google_storage_bucket_object.publisher_zip.name
      }
    }
  }

  service_config {
    max_instance_count    = 5
    available_memory      = "256M"
    timeout_seconds       = 60
    service_account_email = google_service_account.publisher.email
    environment_variables = {
      PROJECT_ID = var.project_id
    }
    secret_environment_variables {
      key        = "SLACK_WEBHOOK_URL"
      project_id = var.project_id
      secret     = google_secret_manager_secret.slack_webhook_url.secret_id
      version    = "latest"
    }
  }

  event_trigger {
    trigger_region        = var.region
    event_type            = "google.cloud.pubsub.topic.v1.messagePublished"
    retry_policy          = "RETRY_POLICY_DO_NOT_RETRY"
    service_account_email = google_service_account.publisher.email
    pubsub_topic          = google_pubsub_topic.topics["publish-video"].id
  }
}

# ==========================================
# API Function (HTTP Trigger)
# ==========================================
data "archive_file" "api_source" {
  type        = "zip"
  source_dir  = "${path.module}/../../backend/api"
  output_path = "${path.module}/api.zip"
}

resource "google_storage_bucket_object" "api_zip" {
  name   = "api-${data.archive_file.api_source.output_md5}.zip"
  bucket = google_storage_bucket.function_source.name
  source = data.archive_file.api_source.output_path
}

resource "google_cloudfunctions2_function" "api" {
  name        = "highlight-api"
  location    = var.region
  description = "API function to fetch jobs"

  build_config {
    runtime     = "python312"
    entry_point = "get_jobs"
    source {
      storage_source {
        bucket = google_storage_bucket.function_source.name
        object = google_storage_bucket_object.api_zip.name
      }
    }
  }

  service_config {
    max_instance_count    = 5
    available_memory      = "256M"
    timeout_seconds       = 30
    service_account_email = google_service_account.api.email
    environment_variables = {
      PROJECT_ID = var.project_id
    }
    secret_environment_variables {
      key        = "IAP_CLIENT_ID"
      project_id = var.project_id
      secret     = google_secret_manager_secret.iap_client_id.secret_id
      version    = "latest"
    }
    secret_environment_variables {
      key        = "IAP_CLIENT_SECRET"
      project_id = var.project_id
      secret     = google_secret_manager_secret.iap_client_secret.secret_id
      version    = "latest"
    }
    secret_environment_variables {
      key        = "IAP_DOMAIN"
      project_id = var.project_id
      secret     = google_secret_manager_secret.iap_domain.secret_id
      version    = "latest"
    }
  }
}

# Allow public access to the API Cloud Function
resource "google_cloud_run_service_iam_member" "api_public" {
  location = google_cloudfunctions2_function.api.location
  project  = google_cloudfunctions2_function.api.project
  service  = google_cloudfunctions2_function.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ==========================================
# Producer Function (Pub/Sub Trigger)
# ==========================================
data "archive_file" "producer_source" {
  type        = "zip"
  source_dir  = "${path.module}/../../backend/producer"
  output_path = "${path.module}/producer.zip"
}

resource "google_storage_bucket_object" "producer_zip" {
  name   = "producer-${data.archive_file.producer_source.output_md5}.zip"
  bucket = google_storage_bucket.function_source.name
  source = data.archive_file.producer_source.output_path
}

resource "google_cloudfunctions2_function" "producer" {
  name        = "job-producer"
  location    = var.region
  description = "Producer function triggered by Pub/Sub"

  build_config {
    runtime     = "python311"
    entry_point = "review_script"
    source {
      storage_source {
        bucket = google_storage_bucket.function_source.name
        object = google_storage_bucket_object.producer_zip.name
      }
    }
  }

  service_config {
    max_instance_count = 5
    available_memory   = "512M"
    timeout_seconds    = 120
    # Reusing the video_analyzer SA since they both use Vertex AI
    service_account_email = google_service_account.video_analyzer.email
    environment_variables = {
      PROJECT_ID = var.project_id
      LOCATION   = var.region
    }
    secret_environment_variables {
      key        = "GEMINI_API_KEY"
      project_id = var.project_id
      secret     = google_secret_manager_secret.gemini_api_key.secret_id
      version    = "latest"
    }
  }

  event_trigger {
    trigger_region        = var.region
    event_type            = "google.cloud.pubsub.topic.v1.messagePublished"
    retry_policy          = "RETRY_POLICY_DO_NOT_RETRY"
    service_account_email = google_service_account.video_analyzer.email
    pubsub_topic          = google_pubsub_topic.topics["review-script"].id
  }
}
