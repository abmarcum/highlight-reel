resource "google_dns_record_set" "ui_dns" {
  project      = "amarcum-argolis-admin"
  managed_zone = "amarcum-demo-altostrat-com"
  name         = "${google_secret_manager_secret_version.iap_domain.secret_data}."
  type         = "A"
  ttl          = 300
  rrdatas      = [google_compute_global_address.ui_ip.address]
}
