resource "google_secret_manager_secret" "gemini_api_key" {
  secret_id = "gemini-api-key"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "gemini_api_key" {
  secret      = google_secret_manager_secret.gemini_api_key.id
  secret_data = var.gemini_api_key
}

# Grant Secret Accessor role to the service account used by Cloud Functions
resource "google_secret_manager_secret_iam_member" "video_analyzer_secret_accessor" {
  secret_id = google_secret_manager_secret.gemini_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.video_analyzer.email}"
}

# ==========================================
# Secret Manager Resources for IAP Credentials
# ==========================================

resource "google_secret_manager_secret" "iap_client_id" {
  secret_id = "iap-client-id"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "iap_client_id" {
  secret      = google_secret_manager_secret.iap_client_id.id
  secret_data = var.iap_client_id
}

resource "google_secret_manager_secret" "iap_client_secret" {
  secret_id = "iap-client-secret"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "iap_client_secret" {
  secret      = google_secret_manager_secret.iap_client_secret.id
  secret_data = var.iap_client_secret
}

resource "google_secret_manager_secret" "iap_domain" {
  secret_id = "iap-domain"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "iap_domain" {
  secret      = google_secret_manager_secret.iap_domain.id
  secret_data = var.iap_domain
}

resource "google_secret_manager_secret_iam_member" "api_secret_accessor_iap_id" {
  secret_id = google_secret_manager_secret.iap_client_id.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

resource "google_secret_manager_secret_iam_member" "api_secret_accessor_iap_secret" {
  secret_id = google_secret_manager_secret.iap_client_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

resource "google_secret_manager_secret_iam_member" "api_secret_accessor_iap_domain" {
  secret_id = google_secret_manager_secret.iap_domain.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

# Grant Gemini API Key secret accessor permissions to API, Renderer, and Cloud Build SAs
resource "google_secret_manager_secret_iam_member" "api_secret_accessor_gemini" {
  secret_id = google_secret_manager_secret.gemini_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

resource "google_secret_manager_secret_iam_member" "renderer_secret_accessor_gemini" {
  secret_id = google_secret_manager_secret.gemini_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.renderer.email}"
}

resource "google_project_iam_member" "cloudbuild_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${data.google_project.project.number}@cloudbuild.gserviceaccount.com"
}

# ==========================================
# Slack Webhook & Proxy Pass Secrets
# ==========================================

resource "google_secret_manager_secret" "slack_webhook_url" {
  secret_id = "slack-webhook-url"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "slack_webhook_url" {
  secret      = google_secret_manager_secret.slack_webhook_url.id
  secret_data = var.slack_webhook_url
}

resource "google_secret_manager_secret_iam_member" "publisher_secret_accessor_slack" {
  secret_id = google_secret_manager_secret.slack_webhook_url.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.publisher.email}"
}

resource "google_secret_manager_secret" "proxy_pass" {
  secret_id = "proxy-pass"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "proxy_pass" {
  secret      = google_secret_manager_secret.proxy_pass.id
  secret_data = var.proxy_pass
}

resource "google_secret_manager_secret_iam_member" "initiator_secret_accessor_proxy" {
  secret_id = google_secret_manager_secret.proxy_pass.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.job_initiator.email}"
}



