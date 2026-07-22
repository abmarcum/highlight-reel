import base64
import json
import logging
import os

import functions_framework
from cloudevents.http import CloudEvent
import google.genai as genai
from google.genai import types
import google.cloud.logging
from google.cloud import bigquery
from google.cloud import storage
import time
import subprocess
import glob
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

PROJECT_ID = os.environ.get("PROJECT_ID")
LOCATION = os.environ.get("LOCATION")
API_KEY = os.environ.get("GEMINI_API_KEY")

def get_app_settings(project_id, dataset_id="highlight_reel_analytics", table_id="app_settings"):
    try:
        bq_client = bigquery.Client()
        query = f"SELECT key, value FROM `{project_id}.{dataset_id}.{table_id}`"
        results = bq_client.query(query).result()
        return {row.key: row.value for row in results}
    except Exception as e:
        logger.error(f"Failed to fetch app settings: {e}")
        return {}

def update_job_status(job_id, status):
    try:
        bq_client = bigquery.Client()
        project_id = os.environ.get("PROJECT_ID", bq_client.project)
        dataset_id = "highlight_reel_analytics"
        table_id = "jobs"
        query = f"""
            UPDATE `{project_id}.{dataset_id}.{table_id}`
            SET status = @status
            WHERE job_id = @job_id
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("status", "STRING", status),
                bigquery.ScalarQueryParameter("job_id", "STRING", str(job_id)),
            ]
        )
        bq_client.query(query, job_config=job_config).result()
        logger.info(f"Successfully updated BigQuery job {job_id} status to {status}")
    except Exception as e:
        logger.warning(f"Failed to update job {job_id} status to {status}: {e}")

def write_error_to_bq(job_id, error_message):
    try:
        bq_client = bigquery.Client()
        project_id = os.environ.get("PROJECT_ID", bq_client.project)
        dataset_id = "highlight_reel_analytics"
        table_id = "jobs"
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

def call_genai_with_retry(client, model_name, contents, config, max_retries=5):
    for attempt in range(max_retries):
        try:
            return client.models.generate_content(
                model=model_name,
                contents=contents,
                config=config
            )
        except Exception as e:
            if ("429" in str(e) or "RESOURCE_EXHAUSTED" in str(e) or "503" in str(e)) and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 10
                logger.warning(f"Gemini API rate limited/busy (429/503). Retrying in {wait_time}s... (Attempt {attempt+1}/{max_retries})")
                time.sleep(wait_time)
            else:
                raise e

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
def analyze_video(cloud_event: CloudEvent) -> None:
    """
    CloudEvent trigger for analyzing a sports video with Gemini Developer API.
    """
    trace_id = None
    span_id = None
    try:
        data = cloud_event.data or {}
        msg = data.get("message", {})
        if "data" in msg:
            dec = json.loads(base64.b64decode(msg["data"]).decode("utf-8"))
            trace_id = dec.get("trace_id")
            span_id = dec.get("span_id")
    except Exception:
        pass

    parent_ctx = extract_parent_context(trace_id, span_id)
    with tracer.start_as_current_span("analyzer-process", context=parent_ctx) as span:
        span.set_attribute("event_id", str(cloud_event.get("id", "unknown")))
        return _analyze_video(cloud_event, span)

def _analyze_video(cloud_event: CloudEvent, span) -> None:
    event_id = cloud_event.get("id", "unknown-event-id")
    logger.info(f"Processing CloudEvent ID: {event_id}")

    try:
        data = cloud_event.data
        if not data or "message" not in data:
            raise ValueError("Invalid CloudEvent payload: missing 'message' field.")

        message = data["message"]
        if "data" not in message:
            raise ValueError("Invalid Pub/Sub message: missing 'data' field.")

        decoded_data = base64.b64decode(message["data"]).decode("utf-8")
        payload = json.loads(decoded_data)
        logger.info(f"Successfully decoded payload for event {event_id}")

    except Exception as e:
        logger.error(f"Failed to parse event data: {e}", exc_info=True)
        return

    video_gcs_uri = payload.get("video_gcs_uri")
    team_player_bias = payload.get("teamPlayerBias", "any")
    tone = payload.get("tone", "neutral")
    language = payload.get("language", "en")
    length_sec = payload.get("length", "60")
    job_id = payload.get("jobId", event_id)
    analysis_mode = payload.get("analysisMode", "video")

    span.set_attribute("job_id", str(job_id))
    span.set_attribute("video_gcs_uri", str(video_gcs_uri))
    span.set_attribute("language", str(language))
    span.set_attribute("tone", str(tone))
    span.set_attribute("length", str(length_sec))

    if not video_gcs_uri:
        logger.error(f"Missing 'video_gcs_uri' in payload for job {job_id}. Aborting.")
        return

    # Check if job was cancelled/deleted
    try:
        bq_client = bigquery.Client()
        project_id_bq = os.environ.get("PROJECT_ID", bq_client.project)
        query = f"SELECT job_id FROM `{project_id_bq}.highlight_reel_analytics.jobs` WHERE job_id = @job_id"
        job_config_bq = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("job_id", "STRING", job_id)]
        )
        results = list(bq_client.query(query, job_config=job_config_bq).result())
        if len(results) == 0:
            logger.info(f"Job {job_id} not found in BigQuery. Assuming it was cancelled. Aborting analysis gracefully.")
            return
    except Exception as e:
        logger.warning(f"Failed to verify job status in BQ, proceeding anyway: {e}")

    # Create a lock to prevent infinite Pub/Sub retry loops for >10m jobs
    try:
        storage_client = storage.Client()
        bucket_name = video_gcs_uri.split("/")[2]
        bucket = storage_client.bucket(bucket_name)
        lock_blob = bucket.blob(f"locks/{job_id}.lock")
        if lock_blob.exists():
            logger.info(f"Job {job_id} is already being processed (lock exists). Skipping retry to prevent infinite loop.")
            return
        lock_blob.upload_from_string(str(time.time()))
    except Exception as e:
        logger.warning(f"Failed to check/create lock file for {job_id}: {e}")

    logger.info(
        f"Job {job_id}: Analyzing video {video_gcs_uri} "
        f"(Bias: '{team_player_bias}', Tone: '{tone}')"
    )

    update_job_status(job_id, "EXTRACTING_AUDIO" if analysis_mode == "audio" else "ANALYZING_SCRIPT")

    try:
        logger.info(f"Job {job_id}: Fetching settings from BigQuery...")
        settings = get_app_settings(project_id=os.environ.get("PROJECT_ID"))
        
        API_KEY = os.environ.get("GEMINI_API_KEY")
        project_id = os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")

        model_name = "gemini-3.5-flash"
        location = os.environ.get("VERTEX_LOCATION", "global")
        logger.info(f"Initializing GenAI Client with Vertex AI (project={project_id}, location={location}, model={model_name})...")
        client = genai.Client(vertexai=True, project=project_id, location=location)
        use_vertex = True

        persona = settings.get("analyzer_persona", "You are a sports video analyst.")
        
        if analysis_mode == "audio":
            prompt = (
                f"{persona}\n\n"
                f"Analyze the sports game audio (crowd roar, announcer excitement, whistles, bat cracks, shoes squeaking) to identify the most thrilling, high-action key plays related to '{team_player_bias}'.\n"
                f"Generate a sports commentary script in a '{tone}' tone. Total combined duration of all clip segments (sum of end_time - start_time) MUST equal EXACTLY {length_sec} seconds.\n"
                f"Language requirement: Output commentary text in language code '{language}'.\n\n"
                f"CRITICAL TIMESTAMP & RELEVANCE RULES:\n"
                f"1. ACCURATE PLAY TIMESTAMPS: Identify the exact start_time (1-2 seconds before the action) and end_time (after the play concludes) for each major play heard in the audio.\n"
                f"2. MATCH COMMENTARY TO ACTION: The commentary `text` for each segment MUST describe the EXACT play occurring within that segment's `[start_time, end_time]` timestamp window.\n"
                f"3. PACING & WORD COUNT: Write approximately 2 words per second of duration for each clip so the commentary finishes before the clip cuts.\n"
                f"4. NO OUT-OF-BOUNDS REFERENCES: Do not mention B-roll or external plays outside this source media.\n"
                f"5. Output format MUST be a JSON array of objects: `text`, `start_time`, `end_time`."
            )
        else:
            prompt = (
                f"{persona}\n\n"
                f"Analyze the video and audio to locate the most exciting, high-impact key plays (goals, dunks, steals, home runs, touchdowns, big hits, key saves) related to '{team_player_bias}'.\n"
                f"Generate a sports commentary script in a '{tone}' tone. Total combined duration of all clip segments (sum of end_time - start_time) MUST equal EXACTLY {length_sec} seconds.\n"
                f"Language requirement: Output commentary text in language code '{language}'.\n\n"
                f"CRITICAL TIMESTAMP & RELEVANCE RULES:\n"
                f"1. ACCURATE VISUAL TIMESTAMPS: Identify the precise start_time (just as the play begins) and end_time (as the reaction finishes) for each visual highlight in the video.\n"
                f"2. MATCH COMMENTARY TO ACTION: The commentary `text` for each segment MUST describe the EXACT play happening on screen during that segment's `[start_time, end_time]` timestamp window.\n"
                f"3. PACING & WORD COUNT: Write approximately 2 words per second of duration for each clip so the commentary finishes before the clip cuts.\n"
                f"4. NO OUT-OF-BOUNDS REFERENCES: Do not mention B-roll or external plays outside this source media.\n"
                f"5. Output format MUST be a JSON array of objects: `text`, `start_time`, `end_time`."
            )

        temp_bucket_name = f"{project_id}-temp-processing"
        cached_audio_blob = None
        try:
            storage_client = storage.Client()
            temp_bucket = storage_client.bucket(temp_bucket_name)
            cached_audio_blob = temp_bucket.blob(f"audio/{job_id}.mp3")
        except Exception:
            pass

        tmp_video_path = f"/tmp/{job_id}_video.mp4"
        tmp_media_path = None

        if use_vertex:
            cached_compressed_blob = temp_bucket.blob(f"compressed/{job_id}.mp4") if temp_bucket else None
            if cached_compressed_blob and cached_compressed_blob.exists():
                logger.info(f"Job {job_id}: Found existing token-optimized media in GCS (gs://{temp_bucket_name}/compressed/{job_id}.mp4). Reusing cached media to skip download & downsampling!")
                compressed_gcs_uri = f"gs://{temp_bucket_name}/compressed/{job_id}.mp4"
                mime_type = "video/mp4"
                media_part = types.Part.from_uri(file_uri=compressed_gcs_uri, mime_type=mime_type)
                logger.info(f"Job {job_id}: Asking Vertex AI ({model_name}) to analyze media ({compressed_gcs_uri})...")
                script_response = call_genai_with_retry(
                    client=client,
                    model_name=model_name,
                    contents=[media_part, prompt],
                    config=types.GenerateContentConfig(response_mime_type="application/json")
                )
            else:
                logger.info(f"Job {job_id}: Downloading video from GCS for token-safe downsampling...")
                storage_client = storage.Client()
                bucket_name = video_gcs_uri.split("/")[2]
                blob_name = "/".join(video_gcs_uri.split("/")[3:])
                bucket = storage_client.bucket(bucket_name)
                blob = bucket.blob(blob_name)

            if not blob.exists():
                logger.warning(f"Job {job_id}: Blob {video_gcs_uri} does not exist directly. Searching fallback GCS locations...")
                try:
                    bq_client = bigquery.Client()
                    project_id_bq = os.environ.get("PROJECT_ID", bq_client.project)
                    query = f"SELECT config FROM `{project_id_bq}.highlight_reel_analytics.jobs` WHERE job_id = @job_id LIMIT 1"
                    job_config_select = bigquery.QueryJobConfig(
                        query_parameters=[bigquery.ScalarQueryParameter("job_id", "STRING", str(job_id))]
                    )
                    res_bq = list(bq_client.query(query, job_config=job_config_select).result())
                    if res_bq and res_bq[0].config:
                        cfg_bq = json.loads(res_bq[0].config) if isinstance(res_bq[0].config, str) else res_bq[0].config
                        alt_uri = cfg_bq.get("video_gcs_uri") or cfg_bq.get("videoUri") or cfg_bq.get("video_uri")
                        if alt_uri and alt_uri != video_gcs_uri:
                            video_gcs_uri = alt_uri
                            bucket_name = video_gcs_uri.split("/")[2]
                            blob_name = "/".join(video_gcs_uri.split("/")[3:])
                            bucket = storage_client.bucket(bucket_name)
                            blob = bucket.blob(blob_name)
                except Exception as search_err:
                    logger.warning(f"Fallback search failed: {search_err}")

            if not blob.exists():
                alt_blob = bucket.blob(f"uploads/{job_id}.mp4")
                if not alt_blob.exists():
                    try:
                        upload_blobs = list(bucket.list_blobs(prefix="uploads/"))
                        mp4_blobs = [b for b in upload_blobs if b.name.endswith(".mp4")]
                        if mp4_blobs:
                            mp4_blobs.sort(key=lambda x: x.updated, reverse=True)
                            alt_blob = mp4_blobs[0]
                            logger.info(f"Job {job_id}: Discovered fallback video in uploads/: {alt_blob.name}")
                    except Exception as list_err:
                        logger.warning(f"Could not list uploads/ directory: {list_err}")

                if alt_blob and alt_blob.exists():
                    blob = alt_blob
                    video_gcs_uri = f"gs://{bucket_name}/{alt_blob.name}"
                else:
                    err_msg = f"Source video file not found in GCS bucket: {video_gcs_uri}"
                    logger.error(err_msg)
                    write_error_to_bq(job_id, err_msg)
                    return

            blob.download_to_filename(tmp_video_path)

            if analysis_mode == "audio":
                logger.info(f"Job {job_id}: Analysis mode is audio only. Extracting audio...")
                tmp_media_path = f"/tmp/{job_id}_audio.mp3"
                subprocess.run([
                    "ffmpeg", "-y", "-i", tmp_video_path,
                    "-q:a", "0", "-map", "a",
                    tmp_media_path
                ], check=True, capture_output=True)
                target_gcs_path = f"audio/{job_id}.mp3"
                mime_type = "audio/mp3"
            else:
                logger.info(f"Job {job_id}: Downsampling resolution & FPS to fit within 1M token context limit...")
                tmp_media_path = f"/tmp/{job_id}_compressed.mp4"
                subprocess.run([
                    "ffmpeg", "-y", "-i", tmp_video_path,
                    "-vf", "scale=-2:480,fps=1",
                    "-c:v", "libx264", "-crf", "30", "-preset", "ultrafast",
                    "-c:a", "aac", "-b:a", "64k",
                    tmp_media_path
                ], check=True, capture_output=True)
                target_gcs_path = f"compressed/{job_id}.mp4"
                mime_type = "video/mp4"

            # Upload downsampled media to GCS temp bucket so Vertex AI can read it via Part.from_uri
            logger.info(f"Job {job_id}: Uploading token-optimized media to gs://{temp_bucket_name}/{target_gcs_path}...")
            temp_blob = temp_bucket.blob(target_gcs_path)
            temp_blob.upload_from_filename(tmp_media_path)
            compressed_gcs_uri = f"gs://{temp_bucket_name}/{target_gcs_path}"

            logger.info(f"Job {job_id}: Asking Vertex AI ({model_name}) to analyze media ({compressed_gcs_uri})...")
            media_part = types.Part.from_uri(file_uri=compressed_gcs_uri, mime_type=mime_type)
            script_response = call_genai_with_retry(
                client=client,
                model_name=model_name,
                contents=[media_part, prompt],
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )

            # Clean up local tmp files
            try:
                if os.path.exists(tmp_video_path): os.remove(tmp_video_path)
                if tmp_media_path and os.path.exists(tmp_media_path): os.remove(tmp_media_path)
            except Exception:
                pass

        else:
            uploaded_files = []
            part_files = []

            if analysis_mode == "audio" and cached_audio_blob and cached_audio_blob.exists():
                logger.info(f"Job {job_id}: Found cached audio in GCS! Reusing cached audio to skip video download.")
                tmp_audio_path = f"/tmp/{job_id}_audio.mp3"
                cached_audio_blob.download_to_filename(tmp_audio_path)
                up_file = client.files.upload(file=tmp_audio_path)
                uploaded_files.append(up_file)
                part_files.append(tmp_audio_path)
            else:
                logger.info(f"Job {job_id}: Downloading video from GCS to local tmp file...")
                storage_client = storage.Client()
                bucket_name = video_gcs_uri.split("/")[2]
                blob_name = "/".join(video_gcs_uri.split("/")[3:])
                bucket = storage_client.bucket(bucket_name)
                blob = bucket.blob(blob_name)
                blob.download_to_filename(tmp_video_path)

                file_size = os.path.getsize(tmp_video_path)
                MAX_SIZE = 1.8 * 1024 * 1024 * 1024 # 1.8GB to be safe
                
                if analysis_mode == "audio":
                    logger.info(f"Job {job_id}: Analysis mode is audio only. Extracting audio...")
                    tmp_audio_path = f"/tmp/{job_id}_audio.mp3"
                    subprocess.run([
                        "ffmpeg", "-y", "-i", tmp_video_path,
                        "-q:a", "0", "-map", "a",
                        tmp_audio_path
                    ], check=True, capture_output=True)
                    
                    try:
                        if cached_audio_blob:
                            cached_audio_blob.upload_from_filename(tmp_audio_path)
                            logger.info(f"Job {job_id}: Cached extracted audio in GCS temp bucket.")
                    except Exception as cache_err:
                        logger.warning(f"Failed to cache audio in GCS: {cache_err}")

                    logger.info(f"Job {job_id}: Uploading audio to Gemini API...")
                    up_file = client.files.upload(file=tmp_audio_path)
                    uploaded_files.append(up_file)
                    part_files.append(tmp_audio_path)
                elif file_size > MAX_SIZE:
                    logger.info(f"Job {job_id}: File is {file_size} bytes (> 1.8GB limit). Downsampling resolution to single lightweight MP4...")
                    compressed_video_path = f"/tmp/{job_id}_compressed.mp4"
                    compress_cmd = [
                        "ffmpeg", "-y", "-i", tmp_video_path,
                        "-vf", "scale=-2:480,fps=1",
                        "-c:v", "libx264", "-crf", "30", "-preset", "ultrafast",
                        "-c:a", "aac", "-b:a", "64k",
                        compressed_video_path
                    ]
                    subprocess.run(compress_cmd, check=True, capture_output=True)
                    part_files.append(compressed_video_path)
                    
                    logger.info(f"Job {job_id}: Uploading compressed video to Gemini API...")
                    up_file = client.files.upload(file=compressed_video_path)
                    uploaded_files.append(up_file)
                else:
                    logger.info(f"Job {job_id}: Uploading video to Gemini API...")
                    up_file = client.files.upload(file=tmp_video_path)
                    uploaded_files.append(up_file)
            
            logger.info(f"Job {job_id}: Waiting for {len(uploaded_files)} file(s) to process...")
            for i, up_file in enumerate(uploaded_files):
                while up_file.state.name == "PROCESSING":
                    time.sleep(2)
                    up_file = client.files.get(name=up_file.name)
                    uploaded_files[i] = up_file
                if up_file.state.name == "FAILED":
                    raise Exception(f"Video processing failed in Gemini API for file {up_file.name}.")

            logger.info(f"Job {job_id}: Upload complete. Asking Gemini API ({model_name}) to analyze the video and audio directly...")
            contents = uploaded_files + [prompt]
            script_response = call_genai_with_retry(
                client=client,
                model_name=model_name,
                contents=contents,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            
            # Cleanup
            try:
                for up_file in uploaded_files:
                    client.files.delete(name=up_file.name)
                os.remove(tmp_video_path)
                for part in part_files:
                    if os.path.exists(part):
                        os.remove(part)
            except Exception as cleanup_err:
                logger.warning(f"Failed to cleanup temp files: {cleanup_err}")
            
        analysis_result = script_response.text
        logger.info(f"Job {job_id}: Analysis complete. Result length: {len(analysis_result)}")

    except Exception as e:
        logger.error(f"Job {job_id}: Vertex AI processing failed: {e}", exc_info=True)
        write_error_to_bq(job_id, str(e))
        # Raise exception to allow Pub/Sub to retry the message for transient errors
        raise e

    # 4. Publish to the next stage (Review Script)
    try:
        publish_to_next_stage(job_id, analysis_result, payload)
    except Exception as e:
        logger.error(f"Job {job_id}: Failed to publish to next stage: {e}", exc_info=True)
        raise e

def publish_to_next_stage(job_id: str, analysis_result: str, original_payload: dict) -> None:
    # Save stage output into BigQuery for Smart Restart
    try:
        bq_client = bigquery.Client()
        project_id = os.environ.get("PROJECT_ID", bq_client.project)
        dataset_id = "highlight_reel_analytics"
        table_id = "jobs"
        
        select_query = f"SELECT config FROM `{project_id}.{dataset_id}.{table_id}` WHERE job_id = @job_id LIMIT 1"
        job_config_select = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("job_id", "STRING", job_id)]
        )
        results = list(bq_client.query(select_query, job_config=job_config_select).result())
        if results and results[0].config:
            cfg = results[0].config
            if isinstance(cfg, str):
                cfg = json.loads(cfg)
            cfg["draft_script"] = analysis_result
            cfg["last_good_stage"] = "ANALYZING_SCRIPT"
            
            update_query = f"UPDATE `{project_id}.{dataset_id}.{table_id}` SET config = PARSE_JSON(@config) WHERE job_id = @job_id"
            job_config_update = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("config", "STRING", json.dumps(cfg)),
                    bigquery.ScalarQueryParameter("job_id", "STRING", job_id)
                ]
            )
            bq_client.query(update_query, job_config=job_config_update).result()
    except Exception as stage_err:
        logger.warning(f"Failed to persist analyzer stage state: {stage_err}")

    from google.cloud import pubsub_v1
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, "review-script")
    data = json.dumps({
        "jobId": job_id, 
        "script": analysis_result,
        "original_payload": original_payload
    }).encode("utf-8")
    publisher.publish(topic_path, data)
    logger.info(f"Job {job_id}: Published to review-script topic")

