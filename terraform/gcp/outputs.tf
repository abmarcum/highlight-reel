output "ui_url" {
  description = "The public URL of the React UI."
  value       = google_cloud_run_v2_service.ui.uri
}

output "api_url" {
  description = "The public URL of the Job API."
  value       = google_cloudfunctions2_function.api.service_config[0].uri
}

resource "local_file" "frontend_env" {
  content  = "VITE_API_URL=/api\nVITE_PROJECT_ID=${var.project_id}\n"
  filename = "${path.module}/../../frontend/.env.production"
}
