# ==========================================
# Identity-Aware Proxy (IAP) & Load Balancer
# ==========================================

# 1. Reserve a Global Static IP for the Load Balancer
resource "google_compute_global_address" "ui_ip" {
  name = "ui-global-ip"
}

# 2. Managed SSL Certificate (Requires a custom domain pointing to the IP above)
resource "google_compute_managed_ssl_certificate" "ui_cert" {
  name = "ui-cert"

  managed {
    domains = [google_secret_manager_secret_version.iap_domain.secret_data]
  }
}

# 3. Serverless Network Endpoint Group (NEG) for Cloud Run
resource "google_compute_region_network_endpoint_group" "ui_neg" {
  name                  = "ui-neg"
  network_endpoint_type = "SERVERLESS"
  region                = var.region
  cloud_run {
    service = google_cloud_run_v2_service.ui.name
  }
}

# 3b. Serverless NEG for API Cloud Function
resource "google_compute_region_network_endpoint_group" "api_neg" {
  name                  = "api-neg"
  network_endpoint_type = "SERVERLESS"
  region                = var.region
  cloud_run {
    # The Cloud Function v2 creates a Cloud Run service under the hood
    service = google_cloudfunctions2_function.api.name
  }
}

# 4. Backend Service with IAP Enabled (UI)
resource "google_compute_backend_service" "ui_backend" {
  name                            = "ui-backend"
  connection_draining_timeout_sec = 0
  load_balancing_scheme           = "EXTERNAL_MANAGED"

  backend {
    group = google_compute_region_network_endpoint_group.ui_neg.id
  }

  iap {
    oauth2_client_id     = google_secret_manager_secret_version.iap_client_id.secret_data
    oauth2_client_secret = google_secret_manager_secret_version.iap_client_secret.secret_data
  }
}

# 4b. Backend Service with IAP Enabled (API)
resource "google_compute_backend_service" "api_backend" {
  name                            = "api-backend"
  connection_draining_timeout_sec = 0
  load_balancing_scheme           = "EXTERNAL_MANAGED"

  backend {
    group = google_compute_region_network_endpoint_group.api_neg.id
  }

  iap {
    oauth2_client_id     = google_secret_manager_secret_version.iap_client_id.secret_data
    oauth2_client_secret = google_secret_manager_secret_version.iap_client_secret.secret_data
  }
}

# 5. URL Map
resource "google_compute_url_map" "ui_url_map" {
  name            = "ui-url-map"
  default_service = google_compute_backend_service.ui_backend.id

  host_rule {
    hosts        = ["*"]
    path_matcher = "allpaths"
  }

  path_matcher {
    name            = "allpaths"
    default_service = google_compute_backend_service.ui_backend.id

    path_rule {
      paths   = ["/api", "/api/*", "/v1/traces", "/v1/logs", "/v1/*"]
      service = google_compute_backend_service.api_backend.id
    }
  }
}

# 6. Target HTTPS Proxy
resource "google_compute_target_https_proxy" "ui_https_proxy" {
  name             = "ui-https-proxy"
  url_map          = google_compute_url_map.ui_url_map.id
  ssl_certificates = [google_compute_managed_ssl_certificate.ui_cert.id]
}

# 7. Global Forwarding Rule (Frontend)
resource "google_compute_global_forwarding_rule" "ui_forwarding_rule" {
  name                  = "ui-forwarding-rule"
  target                = google_compute_target_https_proxy.ui_https_proxy.id
  port_range            = "443"
  ip_address            = google_compute_global_address.ui_ip.id
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

# Output the IP Address so you can point your DNS A Record to it
output "iap_load_balancer_ip" {
  value       = google_compute_global_address.ui_ip.address
  description = "Point your custom domain's A Record to this IP address to provision the SSL cert."
}
