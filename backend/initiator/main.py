import json
import logging
import os
import subprocess

import functions_framework
from cloudevents.http import CloudEvent
from google.cloud import pubsub_v1
from google.cloud import storage
from google.cloud import bigquery

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

# Initialize clients globally for reuse
storage_client = None
publisher = None

PROJECT_ID = os.environ.get("PROJECT_ID")
TOPIC_ID = os.environ.get("TOPIC_ID", "analyze-video")

def get_storage_client():
    global storage_client
    if storage_client is None:
        storage_client = storage.Client()
    return storage_client

def get_app_settings(project_id, dataset_id="highlight_reel_analytics", table_id="app_settings"):
    try:
        bq_client = bigquery.Client()
        query = f"SELECT key, value FROM `{project_id}.{dataset_id}.{table_id}`"
        results = bq_client.query(query).result()
        return {row.key: row.value for row in results}
    except Exception as e:
        logger.error(f"Failed to fetch app settings: {e}")
        return {}

def get_publisher_client():
    global publisher
    if publisher is None:
        publisher = pubsub_v1.PublisherClient()
    return publisher

def write_error_to_bq(job_id, error_message):
    try:
        bq_client = bigquery.Client()
        project_id = os.environ.get("PROJECT_ID", bq_client.project)
        dataset_id = "highlight_reel_analytics"
        table_id = "jobs"
        table_ref = bq_client.dataset(dataset_id).table(table_id)
        
        query = f"""
            UPDATE `{project_id}.{dataset_id}.{table_id}`
            SET status = 'FAILED', error_message = @error_msg
            WHERE job_id = @job_id
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("error_msg", "STRING", str(error_message)),
                bigquery.ScalarQueryParameter("job_id", "STRING", str(job_id)),
            ]
        )
        bq_client.query(query, job_config=job_config).result()
    except Exception as e:
        logger.error(f"Failed to write error to BigQuery: {e}")

import random
from opentelemetry.trace import SpanContext, TraceFlags

def extract_parent_context(trace_id_str: str, parent_span_id_str: str = None):
    if trace_id_str and len(trace_id_str) == 32:
        try:
            trace_id_int = int(trace_id_str, 16)
            span_id_int = int(parent_span_id_str, 16) if parent_span_id_str and len(parent_span_id_str) == 16 else random.getrandbits(64)
            span_context = SpanContext(
                trace_id=trace_id_int,
                span_id=span_id_int,
                is_remote=True,
                trace_flags=TraceFlags(0x01)
            )
            return trace.set_span_in_context(trace.NonRecordingSpan(span_context))
        except Exception:
            pass
    return None

@functions_framework.cloud_event
def process_job(cloud_event: CloudEvent):
    """Triggered by a change to a Cloud Storage bucket.
    Reads a .job file, constructs missing configuration, and publishes to Pub/Sub.
    """
    data = cloud_event.data or {}
    file_name = data.get("name", "")
    bucket_name = data.get("bucket", "")
    trace_id = None
    span_id = None
    if file_name.endswith('.job'):
        try:
            st_client = get_storage_client()
            bkt = st_client.bucket(bucket_name)
            blb = bkt.blob(file_name)
            c_str = blb.download_as_string()
            c_json = json.loads(c_str)
            trace_id = c_json.get("trace_id")
            span_id = c_json.get("span_id")
        except Exception:
            pass

    parent_ctx = extract_parent_context(trace_id, span_id)
    with tracer.start_as_current_span("initiator-process", context=parent_ctx) as span:
        span.set_attribute("bucket", str(bucket_name))
        span.set_attribute("file_name", str(file_name))
        return _process_job(cloud_event, span)

def _process_job(cloud_event: CloudEvent, span):
    """Original implementation."""
    data = cloud_event.data

    # Eventarc GCS events have bucket and name in the data payload
    bucket_name = data.get("bucket")
    file_name = data.get("name")

    if not bucket_name or not file_name:
        logger.error("Missing bucket or name in event data.")
        return

    logger.info(f"Processing file: {file_name} from bucket: {bucket_name}")

    if not file_name.endswith('.job'):
        logger.info(f"File {file_name} does not end with .job, ignoring.")
        return

    try:
        storage_client = get_storage_client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)

        logger.info(f"Downloading {file_name}")
        content = blob.download_as_string()
        
        try:
            job_config = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from {file_name}: {e}")
            return

        logger.info(f"Successfully loaded job config from {file_name}")

        # Check for video_gcs_uri, construct if missing
        video_gcs_uri = job_config.get("video_gcs_uri")
        youtube_url = job_config.get("youtubeUrl")

        if not video_gcs_uri and youtube_url:
            logger.info(f"Downloading YouTube video: {youtube_url}")
            job_id = job_config.get("jobId", "unknown")
            tmp_video_path = f"/tmp/{job_id}_yt.mp4"
            
            cmd = [
            "yt-dlp",
            "-f", "best[ext=mp4][height<=720]/best[ext=mp4]",
            "--extractor-args", "youtube:player_client=default,all;formats=duplicate,missing_pot", "-o", tmp_video_path]
            
            settings = get_app_settings(project_id=os.environ.get("PROJECT_ID", PROJECT_ID))
            if settings.get("proxy_enabled") == "true":
                proxy_host = settings.get("proxy_host", "")
                proxy_user = settings.get("proxy_user", "")
                proxy_pass = os.environ.get("PROXY_PASS") or settings.get("proxy_pass", "")
                
                if proxy_host:
                    if proxy_user and proxy_pass:
                        proxy_url = f"socks5://{proxy_user}:{proxy_pass}@{proxy_host}"
                    else:
                        proxy_url = f"socks5://{proxy_host}"
                    
                    logger.info("Using configured proxy for yt-dlp")
                    cmd.extend(["--proxy", proxy_url])
            else:
                logger.info("Proxy is disabled. Proceeding without proxy.")
            
            cmd.append(youtube_url)
            try:
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                error_msg = f"yt-dlp failed with exit code {e.returncode}. stderr: {e.stderr}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            # Upload to GCS
            dl_blob = bucket.blob(f"downloads/{job_id}.mp4")
            dl_blob.upload_from_filename(tmp_video_path)
            video_gcs_uri = f"gs://{bucket_name}/downloads/{job_id}.mp4"
            job_config["video_gcs_uri"] = video_gcs_uri
            logger.info(f"Uploaded YouTube video to {video_gcs_uri}")
            os.remove(tmp_video_path)

        elif not video_gcs_uri:
            job_id = job_config.get("jobId") or file_name[:-4]
            # Search BigQuery job config for video_gcs_uri
            try:
                bq_client = bigquery.Client()
                project_id_bq = os.environ.get("PROJECT_ID", bq_client.project)
                query = f"SELECT config FROM `{project_id_bq}.highlight_reel_analytics.jobs` WHERE job_id = @job_id LIMIT 1"
                job_config_select = bigquery.QueryJobConfig(
                    query_parameters=[bigquery.ScalarQueryParameter("job_id", "STRING", str(job_id))]
                )
                results = list(bq_client.query(query, job_config=job_config_select).result())
                if results and results[0].config:
                    cfg_data = json.loads(results[0].config) if isinstance(results[0].config, str) else results[0].config
                    video_gcs_uri = cfg_data.get("video_gcs_uri") or cfg_data.get("videoUri") or cfg_data.get("video_uri")
            except Exception as bq_err:
                logger.warning(f"Could not fetch video_gcs_uri from BigQuery for {job_id}: {bq_err}")

            if not video_gcs_uri:
                # Check if file exists under uploads/
                uploads_blob = bucket.blob(f"uploads/{job_id}.mp4")
                if not uploads_blob.exists():
                    try:
                        upload_blobs = list(bucket.list_blobs(prefix="uploads/"))
                        mp4_blobs = [b for b in upload_blobs if b.name.endswith(".mp4")]
                        if mp4_blobs:
                            mp4_blobs.sort(key=lambda x: x.updated, reverse=True)
                            uploads_blob = mp4_blobs[0]
                            logger.info(f"Job {job_id}: Discovered fallback video in uploads/: {uploads_blob.name}")
                    except Exception as list_err:
                        logger.warning(f"Could not list uploads/ directory: {list_err}")

                if uploads_blob and uploads_blob.exists():
                    video_gcs_uri = f"gs://{bucket_name}/{uploads_blob.name}"
                else:
                    video_name = file_name[:-4] + ".mp4"
                    video_gcs_uri = f"gs://{bucket_name}/{video_name}"
            
            job_config["video_gcs_uri"] = video_gcs_uri
            logger.info(f"Resolved video_gcs_uri: {video_gcs_uri}")

        # Publish to Pub/Sub
        publisher = get_publisher_client()
        
        project_id = PROJECT_ID
        if not project_id:
            logger.warning("PROJECT_ID environment variable not set, attempting to detect from default auth.")
            import google.auth
            _, project_id = google.auth.default()

        if not project_id:
            logger.error("Could not determine project ID to publish message.")
            return

        topic_path = publisher.topic_path(project_id, TOPIC_ID)
        message_data = json.dumps(job_config).encode("utf-8")

        logger.info(f"Publishing to topic: {topic_path}")
        future = publisher.publish(topic_path, data=message_data)
        message_id = future.result()

        logger.info(f"Successfully published message {message_id} to {topic_path}")

    except Exception as e:
        logger.error(f"Error processing {file_name}: {e}", exc_info=True)
        job_id = file_name[:-4] if file_name.endswith('.job') else "unknown"
        
        error_str = str(e)
        if "yt-dlp failed" in error_str:
            # Provide a cleaner error message for the UI
            custom_msg = "YouTube Bot Protection Blocked Download. Please use File Upload instead."
            write_error_to_bq(job_id, custom_msg)
            # Do NOT raise the exception so we don't infinitely retry a hard block
            logger.warning("Swallowing yt-dlp bot protection error to prevent infinite retries.")
            return
            
        write_error_to_bq(job_id, error_str)
        raise e
