import base64
import json
import os
import uuid
import datetime

import functions_framework
from google.cloud import texttospeech
from google.cloud import storage
from google.cloud import pubsub_v1
from google.cloud import bigquery
from google.cloud import run_v2

import logging
import google.cloud.logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter

provider = TracerProvider()
cloud_trace_exporter = CloudTraceSpanExporter()
provider.add_span_processor(BatchSpanProcessor(cloud_trace_exporter))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)

try:
    logging_client = google.cloud.logging.Client()
    logging_client.setup_logging()
except Exception:
    logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

# Initialize GCP clients globally to reuse them across invocations
tts_client = None
storage_client = None
publisher = None

PROJECT_ID = os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
RENDER_TOPIC = os.environ.get("RENDER_TOPIC", "render-video")
OUTPUT_BUCKET = os.environ.get("OUTPUT_BUCKET", f"{PROJECT_ID}-temp-processing" if PROJECT_ID else None)

def format_srt_time(seconds_float: float) -> str:
    """Formats time in seconds to SRT time format (HH:MM:SS,mmm)."""
    td = datetime.timedelta(seconds=seconds_float)
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds_int = divmod(remainder, 60)
    milliseconds = td.microseconds // 1000
    return f"{hours:02d}:{minutes:02d}:{seconds_int:02d},{milliseconds:03d}"

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

@functions_framework.cloud_event
def generate_audio(cloud_event):
    """
    Cloud Function triggered by Pub/Sub to generate audio commentary and SRT subtitles.
    """
    with tracer.start_as_current_span("audio_gen-process") as span:
        return _generate_audio(cloud_event, span)

def _generate_audio(cloud_event, span):
    """Original implementation."""
    global tts_client, storage_client, publisher
    if not tts_client:
        tts_client = texttospeech.TextToSpeechClient()
    if not storage_client:
        storage_client = storage.Client()
    if not publisher:
        publisher = pubsub_v1.PublisherClient()

    job_id = "unknown"
    try:
        if cloud_event.data and "message" in cloud_event.data:
            message_data = base64.b64decode(cloud_event.data["message"]["data"]).decode("utf-8")
            payload = json.loads(message_data)
        else:
            logger.error("Invalid cloud event data.")
            return

        job_id = payload.get("jobId", str(uuid.uuid4()))
        script_segments = payload.get("script", [])
        dual_voices = payload.get("dualVoices", False)
        video_uri = payload.get("videoUri") or payload.get("video_gcs_uri")
        if not video_uri:
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
                    video_uri = cfg.get("video_gcs_uri") or cfg.get("videoUri")
            except Exception as bq_err:
                logger.warning(f"Could not fetch video_gcs_uri from BigQuery config: {bq_err}")

        span.set_attribute("job_id", str(job_id))
        span.set_attribute("video_uri", str(video_uri))
        span.set_attribute("dual_voices", bool(dual_voices))

        update_job_status(job_id, "GENERATING_AUDIO")
        
        if not script_segments:
            err_msg = "No script segments found in payload for audio generation."
            logger.error(err_msg)
            write_error_to_bq(job_id, err_msg)
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
                logger.info(f"Job {job_id} not found in BigQuery. Assuming it was cancelled. Aborting audio gen gracefully.")
                return
        except Exception as e:
            logger.warning(f"Failed to verify job status in BQ, proceeding anyway: {e}")

        srt_lines = []
        combined_audio = b""
        
        # Define voices
        voice_str = payload.get("voice", "en-US-Journey-D")
        
        # The frontend provides exact Google TTS voice names
        selected_voice_name = voice_str
        selected_lang_code = selected_voice_name[:5] if len(selected_voice_name) > 5 else "en-US"
        
        # Determine fallback voice (for dual voices)
        voice2_str = payload.get("voice2")
        if voice2_str:
            fallback_voice_name = voice2_str
        else:
            # Simple heuristic: if ends in A/C/F (usually female), use B/D (usually male) and vice versa
            if selected_voice_name.endswith(("A", "C", "F")):
                fallback_voice_name = selected_voice_name[:-1] + ("D" if selected_voice_name.endswith("F") else "B")
            else:
                fallback_voice_name = selected_voice_name[:-1] + ("F" if selected_voice_name.endswith("D") else "A")
                
        fallback_lang_code = fallback_voice_name[:5] if len(fallback_voice_name) > 5 else "en-US"
        
        voice_1 = texttospeech.VoiceSelectionParams(
            language_code=selected_lang_code, name=selected_voice_name
        )
        voice_2 = texttospeech.VoiceSelectionParams(
            language_code=fallback_lang_code, name=fallback_voice_name
        )
        
        current_time = 0.0
        audio_uris = []
        for i, segment in enumerate(script_segments):
            text = segment.get("text") or segment.get("commentary") or segment.get("script") or segment.get("description") or ""
            text = str(text).strip()
            if not text:
                logger.warning(f"Job {job_id}: Segment {i} has empty text. Skipping TTS synthesis for this segment.")
                continue
            orig_start = float(segment.get("start_time", 0.0))
            orig_end = float(segment.get("end_time", orig_start + 1.0))
            duration = orig_end - orig_start
            
            new_start = current_time
            new_end = current_time + duration
            
            # Store new_start in segment so renderer can use it if needed
            segment["new_start"] = new_start
            
            # Build SRT block using sequential time!
            srt_lines.append(str(i + 1))
            srt_lines.append(f"{format_srt_time(new_start)} --> {format_srt_time(new_end)}")
            srt_lines.append(text)
            srt_lines.append("")
            
            # Generate Audio
            synthesis_input = texttospeech.SynthesisInput(text=text)
            
            # Alternate voices if dualVoices is true
            current_voice = voice_2 if dual_voices and (i % 2 != 0) else voice_1
                
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3
            )
            
            response = tts_client.synthesize_speech(
                input=synthesis_input, 
                voice=current_voice, 
                audio_config=audio_config
            )
            
            # Upload individual MP3 to GCS
            bucket = storage_client.bucket(OUTPUT_BUCKET)
            blob_name = f"{job_id}/audio_{i}.mp3"
            audio_blob = bucket.blob(blob_name)
            audio_blob.upload_from_string(response.audio_content, content_type="audio/mpeg")
            
            audio_uris.append(f"gs://{OUTPUT_BUCKET}/{blob_name}")
            
            current_time += duration

        srt_content = "\n".join(srt_lines)
        
        # Upload SRT to GCS
        bucket = storage_client.bucket(OUTPUT_BUCKET)
        
        srt_blob = bucket.blob(f"{job_id}/subtitles.srt")
        srt_blob.upload_from_string(srt_content, content_type="text/plain")
        srt_uri = f"gs://{OUTPUT_BUCKET}/{job_id}/subtitles.srt"
        
        # Execute Cloud Run Job (render-video)
        render_message = payload.copy()
        render_message["audioUris"] = audio_uris
        render_message["srtUri"] = srt_uri
        render_message["videoUri"] = video_uri
        render_message["script"] = script_segments # Now contains new_start
        
        # Save stage output into BigQuery for Smart Restart
        try:
            bq_client = bigquery.Client()
            select_query = f"SELECT config FROM `{PROJECT_ID}.highlight_reel_analytics.jobs` WHERE job_id = @job_id LIMIT 1"
            job_config_select = bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("job_id", "STRING", job_id)]
            )
            results = list(bq_client.query(select_query, job_config=job_config_select).result())
            if results and results[0].config:
                cfg = results[0].config
                if isinstance(cfg, str):
                    cfg = json.loads(cfg)
                cfg["audioUris"] = audio_uris
                cfg["srtUri"] = srt_uri
                cfg["render_script"] = script_segments
                cfg["last_good_stage"] = "AUDIO_GEN"
                
                update_query = f"UPDATE `{PROJECT_ID}.highlight_reel_analytics.jobs` SET config = PARSE_JSON(@config) WHERE job_id = @job_id"
                job_config_update = bigquery.QueryJobConfig(
                    query_parameters=[
                        bigquery.ScalarQueryParameter("config", "STRING", json.dumps(cfg)),
                        bigquery.ScalarQueryParameter("job_id", "STRING", job_id)
                    ]
                )
                bq_client.query(update_query, job_config=job_config_update).result()
        except Exception as stage_err:
            logger.warning(f"Failed to persist audio_gen stage state: {stage_err}")

        try:
            client = run_v2.JobsClient()
            job_name = f"projects/{PROJECT_ID}/locations/us-central1/jobs/video-renderer-job"
            overrides = run_v2.RunJobRequest.Overrides(
                container_overrides=[
                    run_v2.RunJobRequest.Overrides.ContainerOverride(
                        env=[
                            run_v2.EnvVar(name="JOB_PAYLOAD", value=json.dumps(render_message))
                        ]
                    )
                ]
            )
            request = run_v2.RunJobRequest(
                name=job_name,
                overrides=overrides
            )
            logger.info(f"Audio generated, saved to {audio_uris}, subtitles to {srt_uri}. Triggering renderer job: {job_name}")
            operation = client.run_job(request=request)
            logger.info(f"Triggered job successfully. Operation: {operation.operation.name}")
        except Exception as e:
            logger.error(f"Failed to trigger video renderer job: {e}")
            raise e
        
        logger.info(f"Successfully processed audio and SRT for job {job_id}")
    except Exception as e:
        logger.error(f"Error in audio_gen: {e}", exc_info=True)
        write_error_to_bq(job_id, str(e))
        raise e
