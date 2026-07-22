terraform {
  backend "gcs" {
    bucket = "amarcum-argolis-pricing-ewuu3b-tfstate"
    prefix = "terraform/state"
  }
}
