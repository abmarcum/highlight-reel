resource "google_bigquery_dataset" "highlight_reel_dataset" {
  dataset_id                 = "highlight_reel_analytics"
  friendly_name              = "Highlight Reel Analytics"
  description                = "Dataset for job tracking and API costs"
  location                   = var.region
  delete_contents_on_destroy = true
}

resource "google_bigquery_table" "jobs" {
  dataset_id = google_bigquery_dataset.highlight_reel_dataset.dataset_id
  table_id   = "jobs"

  schema = <<EOF
[
  {
    "name": "job_id",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "Unique ID for the job"
  },
  {
    "name": "status",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "PENDING, ANALYZING, RENDERING, COMPLETED, FAILED"
  },
  {
    "name": "created_at",
    "type": "TIMESTAMP",
    "mode": "REQUIRED"
  },
  {
    "name": "config",
    "type": "JSON",
    "mode": "NULLABLE",
    "description": "The full .job config JSON"
  },
  {
    "name": "error_message",
    "type": "STRING",
    "mode": "NULLABLE",
    "description": "Error details if status is FAILED"
  }
]
EOF
}

resource "google_bigquery_table" "costs" {
  dataset_id = google_bigquery_dataset.highlight_reel_dataset.dataset_id
  table_id   = "api_costs"

  schema = <<EOF
[
  {
    "name": "job_id",
    "type": "STRING",
    "mode": "REQUIRED"
  },
  {
    "name": "service",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "e.g., Vertex AI, TTS"
  },
  {
    "name": "tokens_used",
    "type": "INTEGER",
    "mode": "NULLABLE"
  },
  {
    "name": "estimated_cost_usd",
    "type": "FLOAT",
    "mode": "NULLABLE"
  }
]
EOF
}

resource "google_bigquery_table" "user_roles" {
  dataset_id = google_bigquery_dataset.highlight_reel_dataset.dataset_id
  table_id   = "user_roles"

  schema = <<EOF
[
  {
    "name": "email",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "User email address"
  },
  {
    "name": "role",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "admin, user, viewer"
  }
]
EOF
}

resource "google_bigquery_table" "app_settings" {
  dataset_id = google_bigquery_dataset.highlight_reel_dataset.dataset_id
  table_id   = "app_settings"

  schema = <<EOF
[
  {
    "name": "key",
    "type": "STRING",
    "mode": "REQUIRED"
  },
  {
    "name": "value",
    "type": "STRING",
    "mode": "REQUIRED"
  }
]
EOF
}
