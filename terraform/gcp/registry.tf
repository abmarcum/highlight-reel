resource "google_artifact_registry_repository" "highlight_repo" {
  location      = var.region
  repository_id = "highlight-repo"
  description   = "Docker repository for Highlight Reel Enterprise"
  format        = "DOCKER"
}
