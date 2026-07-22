import base64
import json
import datetime
import os
import requests
import functions_framework
from google.cloud import bigquery

import logging
import google.cloud.logging
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter

    provider = TracerProvider()
    cloud_trace_exporter = CloudTraceSpanExporter()
    provider.add_span_processor(BatchSpanProcessor(cloud_trace_exporter))
    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer(__name__)
except Exception as otel_err:
    print(f"OpenTelemetry initialization warning: {otel_err}")
    from opentelemetry import trace
    tracer = trace.get_tracer(__name__)

try:
    logging_client = google.cloud.logging.Client()
    logging_client.setup_logging()
except Exception:
    logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

# Initialize BigQuery client
# Note: In a real Google Cloud environment, the project is inferred automatically.
bq_client = bigquery.Client()
dataset_id = "highlight_reel_analytics"
table_id = "jobs"

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

@functions_framework.cloud_event
def publish_video(cloud_event):
    """
    Cloud Function triggered by Pub/Sub topic `publish-video`.
    """
    with tracer.start_as_current_span("publisher-process") as span:
        return _publish_video(cloud_event, span)

def _publish_video(cloud_event, span):
    """Original implementation."""
    try:
        # Extract payload from the event
        pubsub_message = base64.b64decode(cloud_event.data["message"]["data"]).decode("utf-8")
        payload = json.loads(pubsub_message)
        
        job_id = payload.get("jobId")
        final_video_uri = payload.get("final_video_uri")
        
        span.set_attribute("job_id", str(job_id))
        span.set_attribute("final_video_uri", str(final_video_uri))
        
        if not job_id or not final_video_uri:
            logger.error("Missing jobId or final_video_uri in payload.")
            return

        logger.info(f"Processing job {job_id} with video {final_video_uri}")

        # 1. Update row in BigQuery
        project_id_bq = os.environ.get("PROJECT_ID", bq_client.project)
        
        # We store the final_video_uri inside the JSON config to match the schema
        payload["final_video_uri"] = final_video_uri
        
        update_query = f"""
            UPDATE `{project_id_bq}.{dataset_id}.{table_id}`
            SET status = 'COMPLETED', error_message = NULL, config = PARSE_JSON(@config)
            WHERE job_id = @job_id
        """
        job_config_bq = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("job_id", "STRING", str(job_id)),
                bigquery.ScalarQueryParameter("config", "STRING", json.dumps(payload)),
            ]
        )
        try:
            bq_client.query(update_query, job_config=job_config_bq).result()
            logger.info(f"Successfully updated job {job_id} in BigQuery to COMPLETED.")
        except Exception as e:
            logger.error(f"Encountered errors while updating BigQuery: {e}")
            
        # 2. Mock sending Slack webhook notification
        slack_payload = {
            "text": f"Video processing completed for job {job_id}. Video available at: {final_video_uri}"
        }
        
        logger.info(f"Mocking Slack notification to {SLACK_WEBHOOK_URL} with payload: {slack_payload}")
        try:
            response = requests.post(SLACK_WEBHOOK_URL, json=slack_payload)
            logger.info(f"Slack response status: {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Mock Slack notification failed (expected if mock URL is used): {e}")
        
    except Exception as e:
        logger.error(f"Error processing pubsub message: {e}")
