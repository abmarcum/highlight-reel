import os
import json
import subprocess
from urllib.parse import urlparse
from google.cloud import storage
from google.cloud import pubsub_v1
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

def download_blob(storage_client, gcs_uri, destination_file_name):
    """Downloads a blob from the bucket."""
    if not gcs_uri:
        return
    parsed_uri = urlparse(gcs_uri)
    bucket_name = parsed_uri.netloc
    blob_name = parsed_uri.path.lstrip('/')
    
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.download_to_filename(destination_file_name)
    logger.info(f"Downloaded {gcs_uri} to {destination_file_name}")

def upload_blob(storage_client, bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the bucket."""
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_name)
    logger.info(f"File {source_file_name} uploaded to gs://{bucket_name}/{destination_blob_name}")
    return f"gs://{bucket_name}/{destination_blob_name}"

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

def main():
    job_payload_str = os.environ.get('JOB_PAYLOAD')
    trace_id = None
    span_id = None
    if job_payload_str:
        try:
            p_json = json.loads(job_payload_str)
            trace_id = p_json.get("trace_id")
            span_id = p_json.get("span_id")
        except Exception:
            pass

    parent_ctx = extract_parent_context(trace_id, span_id)
    with tracer.start_as_current_span("renderer-process", context=parent_ctx) as span:
        return _main(span)

def _main(span):
    # 1. Read configuration from environment variables
    job_payload_str = os.environ.get('JOB_PAYLOAD')
    if not job_payload_str:
        logger.warning("JOB_PAYLOAD environment variable is not set. Attempting BigQuery fallback...")
        payload = {}
    else:
        try:
            payload = json.loads(job_payload_str)
        except Exception:
            payload = {}
    
    job_id = payload.get('jobId') or payload.get('job_id')
    if not job_id:
        try:
            bq_client = bigquery.Client()
            project_id_bq = os.environ.get("PROJECT_ID", bq_client.project)
            query = f"SELECT job_id FROM `{project_id_bq}.highlight_reel_analytics.jobs` ORDER BY created_at DESC LIMIT 1"
            res = list(bq_client.query(query).result())
            if res:
                job_id = res[0].job_id
                logger.info(f"Fallback selected latest job {job_id} from BigQuery.")
        except Exception as fetch_err:
            logger.warning(f"Could not fetch latest job_id from BigQuery: {fetch_err}")

    if not job_id:
        job_id = 'final'

    video_uri = payload.get('videoUri') or payload.get('video_uri') or payload.get('video_gcs_uri')
    audio_uri = payload.get('audioUri') or payload.get('audio_uri')
    srt_uri = payload.get('srtUri') or payload.get('srt_uri')
    # Fetch configuration fallbacks from BigQuery if job_id is available
    if job_id:
        try:
            bq_client = bigquery.Client()
            project_id_bq = os.environ.get("PROJECT_ID", bq_client.project)
            query = f"SELECT config FROM `{project_id_bq}.highlight_reel_analytics.jobs` WHERE job_id = @job_id LIMIT 1"
            job_config_select = bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("job_id", "STRING", job_id)]
            )
            results = list(bq_client.query(query, job_config=job_config_select).result())
            if results and results[0].config:
                cfg = results[0].config
                if isinstance(cfg, str):
                    cfg = json.loads(cfg)
                if not video_uri:
                    video_uri = cfg.get("video_gcs_uri") or cfg.get("videoUri") or cfg.get("video_uri")
                if not audio_uri:
                    audio_uri = cfg.get("audioUri") or cfg.get("audio_uri")
                if not srt_uri:
                    srt_uri = cfg.get("srtUri") or cfg.get("srt_uri")
                if not payload.get('audioUris'):
                    payload['audioUris'] = cfg.get("audioUris") or cfg.get("audio_uris") or []
                if not payload.get('script'):
                    payload['script'] = cfg.get("render_script") or cfg.get("final_script") or cfg.get("script") or []
        except Exception as bq_err:
            logger.warning(f"Could not fetch config from BigQuery in renderer: {bq_err}")

    aspect_ratio = payload.get('aspectRatio', '16:9')
    project_id = payload.get('project_id') or os.environ.get('PROJECT_ID') or os.environ.get('GOOGLE_CLOUD_PROJECT')
    output_bucket = payload.get('output_bucket') or f'{project_id}-processed-highlights'
    output_filename = payload.get('output_filename', f'{job_id}.mp4')
    topic_id = payload.get('topic_id', 'publish-video')

    span.set_attribute("video_uri", str(video_uri))
    span.set_attribute("audio_uri", str(audio_uri))
    span.set_attribute("srt_uri", str(srt_uri))
    span.set_attribute("output_bucket", str(output_bucket))
    span.set_attribute("output_filename", str(output_filename))

    update_job_status(job_id, "RENDERING_VIDEO")
    
    try:
        bq_client = bigquery.Client()
        project_id_bq = os.environ.get("PROJECT_ID", bq_client.project)
        query = f"SELECT job_id FROM `{project_id_bq}.highlight_reel_analytics.jobs` WHERE job_id = @job_id"
        job_config_bq = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("job_id", "STRING", job_id)]
        )
        results = list(bq_client.query(query, job_config=job_config_bq).result())
        if len(results) == 0:
            logger.info(f"Job {job_id} not found in BigQuery. Assuming it was cancelled. Aborting renderer gracefully.")
            return
    except Exception as e:
        logger.warning(f"Failed to verify job status in BQ, proceeding anyway: {e}")

    storage_client = storage.Client()
    
    # Verify video_uri exists or fallback to raw video bucket
    if not video_uri:
        try:
            raw_bucket_name = f"{project_id}-raw-videos"
            raw_bucket = storage_client.bucket(raw_bucket_name)
            for blob in raw_bucket.list_blobs(prefix="uploads/"):
                if blob.name.endswith(".mp4"):
                    video_uri = f"gs://{raw_bucket_name}/{blob.name}"
                    logger.info(f"Job {job_id}: Found fallback raw video ({video_uri}).")
                    break
        except Exception as raw_err:
            logger.warning(f"Job {job_id}: Could not check raw video fallback: {raw_err}")

    if not video_uri:
        raise ValueError("JOB_PAYLOAD must contain video_uri.")

    # 2. Download assets to /tmp/
    tmp_video = '/tmp/input_video.mp4'
    tmp_srt = '/tmp/input_subtitles.srt' if srt_uri else None
    tmp_output = '/tmp/final_output.mp4'
    
    download_blob(storage_client, video_uri, tmp_video)
    if tmp_srt:
        download_blob(storage_client, srt_uri, tmp_srt)
        
    script_segments = payload.get('script', [])
    if not script_segments:
        logger.warning("No script segments found. Using default full-video duration.")
        script_segments = [{"start_time": 0.0, "end_time": 60.0}]
    concat_txt_path = '/tmp/concat.txt'
    with open(concat_txt_path, 'w') as f:
        for segment in script_segments:
            start_time = float(segment.get("start_time", 0.0))
            end_time = float(segment.get("end_time", start_time + 1.0))
            f.write(f"file '{tmp_video}'\n")
            f.write(f"inpoint {start_time}\n")
            f.write(f"outpoint {end_time}\n")
            
    audio_uris = payload.get('audioUris', [])
    for i, a_uri in enumerate(audio_uris):
        download_blob(storage_client, a_uri, f'/tmp/audio_{i}.mp3')
    
    music_track = payload.get('musicTrack', 'none')
    
    # 3. Construct and run ffmpeg command
    ffmpeg_cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', concat_txt_path]
    
    # Input mapping index tracker
    current_input_idx = 1
    
    audio_idx_start = current_input_idx
    for i in range(len(audio_uris)):
        ffmpeg_cmd.extend(['-i', f'/tmp/audio_{i}.mp3'])
        current_input_idx += 1
        
    if music_track != "none":
        tmp_music = '/tmp/input_music.mp3'
        # Generate a synthetic mock music track (a low hum for orchestral, beep for electronic, etc.)
        # For a true production app, we would download from a GCS bucket here.
        synth_freq = "440" if music_track == "electronic" else "220" if music_track == "hiphop" else "330"
        logger.info(f"Generating mock {music_track} music track...")
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency={synth_freq}:duration=60", tmp_music], check=True)
        ffmpeg_cmd.extend(['-i', tmp_music])
        music_idx = current_input_idx
        current_input_idx += 1
    else:
        music_idx = None
        
    filters = []
    video_in = "[0:v]"
    video_map = "0:v"
    audio_map = "0:a"
    
    # 1. Aspect Ratio Cropping
    if aspect_ratio == "9:16":
        filters.append(f"{video_in}crop=ih*9/16:ih[vcrop]")
        video_in = "[vcrop]"
        video_map = "[vcrop]"
    elif aspect_ratio == "1:1":
        filters.append(f"{video_in}crop=ih:ih[vcrop]")
        video_in = "[vcrop]"
        video_map = "[vcrop]"
    
    # 2. Subtitles
    enable_subtitles = payload.get('enableSubtitles')
    if enable_subtitles is None:
        enable_subtitles = payload.get('enable_subtitles')
    if enable_subtitles is None and 'cfg' in locals() and cfg:
        enable_subtitles = cfg.get('enableSubtitles') or cfg.get('enable_subtitles')

    if isinstance(enable_subtitles, str):
        enable_subtitles = enable_subtitles.lower() in ('true', '1', 'yes')
    else:
        enable_subtitles = bool(enable_subtitles)

    if tmp_srt and enable_subtitles:
        logger.info(f"Job {job_id}: Subtitles enabled. Burning subtitles from {tmp_srt}.")
        filters.append(f"{video_in}subtitles={tmp_srt}[vout]")
        video_in = "[vout]"
        video_map = "[vout]"
    else:
        logger.info(f"Job {job_id}: Subtitles disabled or missing (enable_subtitles={enable_subtitles}). Skipping subtitle overlay.")
        
    # Audio Mixing Logic
    mix_inputs = []
    
    # Always keep original audio, ducked
    filters.append("[0:a]volume=0.2[a0]")
    mix_inputs.append("[a0]")
    
    for i, segment in enumerate(script_segments):
        if i < len(audio_uris):
            delay_ms = int(float(segment.get('new_start', 0.0)) * 1000)
            filters.append(f"[{audio_idx_start + i}:a]adelay={delay_ms}|{delay_ms},volume=1.0[a_voice_{i}]")
            mix_inputs.append(f"[a_voice_{i}]")
            
    if music_idx is not None:
        filters.append(f"[{music_idx}:a]volume=0.1[a_music]")
        mix_inputs.append("[a_music]")
        
    if len(mix_inputs) > 1:
        inputs_str = "".join(mix_inputs)
        filters.append(f"{inputs_str}amix=inputs={len(mix_inputs)}:duration=first[aout]")
        audio_map = "[aout]"
    elif len(mix_inputs) == 1:
        audio_map = mix_inputs[0]
        
    if filters:
        ffmpeg_cmd.extend(['-filter_complex', ';'.join(filters)])
        
    ffmpeg_cmd.extend(['-map', video_map, '-map', audio_map])
    
    if tmp_srt:
        ffmpeg_cmd.extend(['-c:v', 'libx264'])
    else:
        # Since we use complex filters for audio and potentially video crop, we must re-encode anyway.
        ffmpeg_cmd.extend(['-c:v', 'libx264'])
        
    ffmpeg_cmd.extend(['-c:a', 'aac'])
        
    # We no longer strictly truncate to length, the concat handles the exact segments!
    ffmpeg_cmd.append(tmp_output)
    
    logger.info(f"Running ffmpeg command: {' '.join(ffmpeg_cmd)}")
    subprocess.run(ffmpeg_cmd, check=True)
    
    # 4. Upload resulting final.mp4 back to GCS
    final_gcs_uri = upload_blob(storage_client, output_bucket, tmp_output, output_filename)
    
    # 5. Publish completion message to Pub/Sub
    if project_id and topic_id:
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(project_id, topic_id)
        
        message_data = {
            "status": "COMPLETED",
            "final_video_uri": final_gcs_uri,
            "jobId": payload.get("jobId"),
            "original_payload": payload
        }
        data_str = json.dumps(message_data)
        data = data_str.encode("utf-8")
        
        future = publisher.publish(topic_path, data)
        message_id = future.result()
        logger.info(f"Published completion message to {topic_path} with ID {message_id}")
    else:
        logger.warning("Project ID or Topic ID not provided. Skipping Pub/Sub publish.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Error in renderer: {e}", exc_info=True)
        job_payload_str = os.environ.get('JOB_PAYLOAD', '{}')
        try:
            payload = json.loads(job_payload_str)
            job_id = payload.get('jobId', 'unknown')
        except:
            job_id = 'unknown'
        write_error_to_bq(job_id, str(e))
        raise e
