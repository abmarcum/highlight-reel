resource "google_service_account" "job_initiator" {
  account_id   = "job-initiator-sa"
  display_name = "Job Initiator Service Account"
}

resource "google_service_account" "video_analyzer" {
  account_id   = "video-analyzer-sa"
  display_name = "Video Analyzer Service Account"
}

# ---------------------------------------------------------
# Job Initiator IAM
# ---------------------------------------------------------

resource "google_storage_bucket_iam_member" "job_initiator_raw" {
  bucket = "${var.project_id}-raw-videos"
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.job_initiator.email}"
}

# Publish access to Pub/Sub
resource "google_project_iam_member" "job_initiator_pubsub" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.job_initiator.email}"
}

# Eventarc receiver (needed to receive Eventarc triggers)
resource "google_project_iam_member" "job_initiator_eventarc" {
  project = var.project_id
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:${google_service_account.job_initiator.email}"
}

# Cloud Run invoker (Cloud Functions v2 run on Cloud Run, Eventarc needs to invoke it)
resource "google_project_iam_member" "job_initiator_trace" {
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.job_initiator.email}"
}

resource "google_project_iam_member" "job_initiator_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.job_initiator.email}"
}

resource "google_project_iam_member" "job_initiator_bq_data" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.job_initiator.email}"
}

resource "google_project_iam_member" "job_initiator_bq_job" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.job_initiator.email}"
}

# ---------------------------------------------------------
# Video Analyzer IAM
# ---------------------------------------------------------

resource "google_storage_bucket_iam_member" "video_analyzer_raw" {
  bucket = "${var.project_id}-raw-videos"
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.video_analyzer.email}"
}

resource "google_storage_bucket_iam_member" "video_analyzer_temp" {
  bucket = "${var.project_id}-temp-processing"
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.video_analyzer.email}"
}

# Publish access to Pub/Sub
resource "google_project_iam_member" "video_analyzer_pubsub" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.video_analyzer.email}"
}

resource "google_project_iam_member" "video_analyzer_aiplatform" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.video_analyzer.email}"
}

resource "google_project_iam_member" "video_analyzer_bq_data" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.video_analyzer.email}"
}

resource "google_project_iam_member" "video_analyzer_bq_job" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.video_analyzer.email}"
}

# Eventarc receiver
resource "google_project_iam_member" "video_analyzer_eventarc" {
  project = var.project_id
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:${google_service_account.video_analyzer.email}"
}

# Cloud Run invoker
resource "google_project_iam_member" "video_analyzer_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.video_analyzer.email}"
}

resource "google_project_iam_member" "video_analyzer_trace" {
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.video_analyzer.email}"
}

# ---------------------------------------------------------
# Cloud Storage Service Agent Role
# Required for GCS Eventarc triggers to publish to Pub/Sub
# ---------------------------------------------------------
data "google_storage_project_service_account" "gcs_account" {}

resource "google_project_iam_member" "gcs_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${data.google_storage_project_service_account.gcs_account.email_address}"
}

# ---------------------------------------------------------
# Audio Gen IAM
# ---------------------------------------------------------
resource "google_service_account" "audio_gen" {
  account_id   = "audio-gen-sa"
  display_name = "Audio Gen Service Account"
}

resource "google_storage_bucket_iam_member" "audio_gen_temp" {
  bucket = "${var.project_id}-temp-processing"
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.audio_gen.email}"
}

resource "google_storage_bucket_iam_member" "audio_gen_processed" {
  bucket = "${var.project_id}-processed-highlights"
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.audio_gen.email}"
}

resource "google_project_iam_member" "audio_gen_pubsub" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.audio_gen.email}"
}

resource "google_project_iam_member" "audio_gen_run_invoker" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.audio_gen.email}"
}

resource "google_project_iam_member" "audio_gen_bq_data" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.audio_gen.email}"
}

resource "google_project_iam_member" "audio_gen_bq_job" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.audio_gen.email}"
}

resource "google_project_iam_member" "audio_gen_trace" {
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.audio_gen.email}"
}

# ---------------------------------------------------------
# Renderer IAM
# ---------------------------------------------------------
resource "google_service_account" "renderer" {
  account_id   = "renderer-sa"
  display_name = "Renderer Service Account"
}

resource "google_storage_bucket_iam_member" "renderer_raw_viewer" {
  bucket = "${var.project_id}-raw-videos"
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.renderer.email}"
}

resource "google_storage_bucket_iam_member" "renderer_temp_viewer" {
  bucket = "${var.project_id}-temp-processing"
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.renderer.email}"
}

resource "google_storage_bucket_iam_member" "renderer_processed_admin" {
  bucket = "${var.project_id}-processed-highlights"
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.renderer.email}"
}

resource "google_project_iam_member" "renderer_pubsub" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.renderer.email}"
}

resource "google_project_iam_member" "renderer_bq_data" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.renderer.email}"
}

resource "google_project_iam_member" "renderer_bq_job" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.renderer.email}"
}

resource "google_project_iam_member" "renderer_trace" {
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.renderer.email}"
}

# ---------------------------------------------------------
# Publisher IAM
# ---------------------------------------------------------
resource "google_service_account" "publisher" {
  account_id   = "publisher-sa"
  display_name = "Publisher Service Account"
}

resource "google_project_iam_member" "publisher_bq" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.publisher.email}"
}

resource "google_project_iam_member" "publisher_bq_job" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.publisher.email}"
}

resource "google_project_iam_member" "publisher_trace" {
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.publisher.email}"
}

resource "google_project_iam_member" "publisher_eventarc" {
  project = var.project_id
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:${google_service_account.publisher.email}"
}

resource "google_project_iam_member" "publisher_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.publisher.email}"
}

# ---------------------------------------------------------
# Cloud Build IAM (for CI/CD deployments)
# ---------------------------------------------------------
data "google_project" "project" {}

resource "google_project_iam_member" "cloudbuild_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${data.google_project.project.number}@cloudbuild.gserviceaccount.com"
}

resource "google_project_iam_member" "cloudbuild_sa_user" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${data.google_project.project.number}@cloudbuild.gserviceaccount.com"
}

# ---------------------------------------------------------
# API Function IAM
# ---------------------------------------------------------
resource "google_service_account" "api" {
  account_id   = "highlight-api-sa"
  display_name = "API Service Account"
}

resource "google_project_iam_member" "api_bq_reader" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_bq_jobuser" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_storage_bucket_iam_member" "api_raw_admin" {
  bucket = "${var.project_id}-raw-videos"
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.api.email}"
}

resource "google_storage_bucket_iam_member" "api_processed_admin" {
  bucket = "${var.project_id}-processed-highlights"
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.api.email}"
}

resource "google_storage_bucket_iam_member" "api_temp_admin" {
  bucket = "${var.project_id}-temp-processing"
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_logging_viewer" {
  project = var.project_id
  role    = "roles/logging.viewer"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_token_creator" {
  project = var.project_id
  role    = "roles/iam.serviceAccountTokenCreator"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_trace" {
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_run_developer" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "renderer_logging_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.renderer.email}"
}
