locals {
  topics = [
    "analyze-video",
    "review-script",
    "generate-audio",
    "render-video",
    "publish-video"
  ]
}

resource "google_pubsub_topic" "topics" {
  for_each = toset(local.topics)
  name     = each.key
}

# Optional: Add subscriptions if cloud functions aren't auto-creating them
resource "google_pubsub_subscription" "subscriptions" {
  for_each = toset(local.topics)
  name     = "${each.key}-sub"
  topic    = google_pubsub_topic.topics[each.key].name
}
