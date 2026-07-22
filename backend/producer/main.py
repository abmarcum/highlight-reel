import base64
import json
import logging
import os
import re

import functions_framework
from cloudevents.http import CloudEvent
import google.genai as genai
from google.genai import types

from google.cloud import bigquery
from google.cloud import pubsub_v1

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

PROJECT_ID = os.environ.get("PROJECT_ID")
LOCATION = os.environ.get("LOCATION", "us-central1")
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
def review_script(cloud_event: CloudEvent) -> None:
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
    with tracer.start_as_current_span("producer-process", context=parent_ctx) as span:
        span.set_attribute("event_id", str(cloud_event.get("id", "unknown")))
        return _review_script(cloud_event, span)

def _review_script(cloud_event: CloudEvent, span) -> None:
    event_id = cloud_event.get("id", "unknown-event-id")
    logger.info(f"Processing CloudEvent ID: {event_id}")

    try:
        data = cloud_event.data
        message = data["message"]
        decoded_data = base64.b64decode(message["data"]).decode("utf-8")
        payload = json.loads(decoded_data)
    except Exception as e:
        logger.error(f"Failed to parse event data: {e}", exc_info=True)
        return

    job_id = payload.get("jobId", event_id)
    script_and_timestamps = payload.get("script")
    original_payload = payload.get("original_payload", {})
    
    tone = original_payload.get("tone", "neutral")
    bias = original_payload.get("teamPlayerBias", "any")
    length_sec = original_payload.get("length", "60")

    span.set_attribute("job_id", str(job_id))
    
    update_job_status(job_id, "REVIEWING_SCRIPT")
    logger.info(f"Job {job_id}: Producer agent reviewing script.")

    try:
        settings = get_app_settings(project_id=os.environ.get("PROJECT_ID"))
        
        API_KEY = os.environ.get("GEMINI_API_KEY")
        project_id = os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")

        model_name = "gemini-3.5-flash"
        location = os.environ.get("VERTEX_LOCATION", "global")
        logger.info(f"Initializing GenAI Client with Vertex AI (project={project_id}, location={location}, model={model_name})...")
        client = genai.Client(vertexai=True, project=project_id, location=location)

        persona = settings.get("producer_persona", "You are the Executive Producer of a sports highlight show. Your job is to review the following draft script and selected timestamps generated by the junior analyst.")
        
        prompt = (
            f"{persona}\n\n"
            f"Draft Script & Timestamps (JSON):\n{script_and_timestamps}\n\n"
            f"Target Tone: {tone}\n"
            f"Target Bias/Focus: {bias}\n"
            f"Target Total Clip Length: {length_sec} seconds\n\n"
            f"CRITICAL TIMING & RELEVANCE INSTRUCTIONS:\n"
            f"1. PRESERVE VIDEO TIMESTAMPS: The `start_time` and `end_time` values in the draft script represent actual visual plays extracted from the source video. You MUST keep these start_time and end_time values unchanged (or trim slightly if needed), so the video clips cut by FFmpeg match the action.\n"
            f"2. MATCH COMMENTARY TO THE PLAY: Rewrite the commentary `text` for each segment so it describes the EXACT play happening in that specific timestamp range with high energy and relevance to '{bias}'.\n"
            f"3. STRICT WORD PACING: The commentary text length MUST match the duration (end_time - start_time) of each clip. Write approximately 2 to 2.3 words per second of clip duration (e.g., a 6-second clip needs 12-14 words max) so the voiceover completes before the video clip cuts to the next play.\n"
            f"4. Do NOT invent new timestamps or reference out-of-bounds video content.\n"
            f"5. Ensure the output is a JSON list of objects: `text`, `start_time`, and `end_time`."
        )
        
        response = call_genai_with_retry(
            client=client,
            model_name=model_name, 
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "text": types.Schema(type=types.Type.STRING),
                            "start_time": types.Schema(type=types.Type.NUMBER),
                            "end_time": types.Schema(type=types.Type.NUMBER)
                        }
                    )
                )
            )
        )
        resp_text = (response.text or "").strip()
        if resp_text.startswith("```json"):
            resp_text = resp_text[7:]
        if resp_text.startswith("```"):
            resp_text = resp_text[3:]
        if resp_text.endswith("```"):
            resp_text = resp_text[:-3]
        resp_text = resp_text.strip()

        try:
            final_script = json.loads(resp_text)
        except json.JSONDecodeError as err:
            logger.warning(f"Job {job_id}: Standard json.loads failed ({err}), attempting regex array extraction...")
            match = re.search(r'\[.*\]', resp_text, re.DOTALL)
            if match:
                try:
                    final_script = json.loads(match.group(0))
                except Exception as inner_err:
                    raise Exception(f"Failed to parse producer JSON response: {inner_err}")
            else:
                raise Exception(f"Failed to parse producer JSON response: {err}")

        # Enforce exact requested clip length (target_length)
        try:
            target_length = float(length_sec)
        except (ValueError, TypeError):
            target_length = 60.0

        if final_script and isinstance(final_script, list):
            current_total = sum(max(0.1, float(seg.get("end_time", 0)) - float(seg.get("start_time", 0))) for seg in final_script)
            if current_total > 0 and abs(current_total - target_length) > 1.0:
                logger.info(f"Job {job_id}: Adjusting clip segment durations from {current_total:.1f}s to match target length of {target_length:.1f}s")
                scale = target_length / current_total
                accumulated = 0.0
                for i, seg in enumerate(final_script):
                    start = float(seg.get("start_time", 0.0))
                    end = float(seg.get("end_time", start + 1.0))
                    orig_dur = max(0.1, end - start)
                    
                    if i == len(final_script) - 1:
                        new_dur = max(0.5, round(target_length - accumulated, 2))
                    else:
                        new_dur = max(0.5, round(orig_dur * scale, 2))
                        accumulated += new_dur
                    
                    seg["start_time"] = round(start, 2)
                    seg["end_time"] = round(start + new_dur, 2)

        logger.info(f"Job {job_id}: Producer agent finished review. Final script segments: {len(final_script)}")

    except Exception as e:
        logger.error(f"Job {job_id}: Producer agent failed: {e}", exc_info=True)
        write_error_to_bq(job_id, str(e))
        raise e

    # Publish to next stage (generate-audio)
    try:
        # Save stage output into BigQuery for Smart Restart
        try:
            bq_client = bigquery.Client()
            project_id_bq = os.environ.get("PROJECT_ID", bq_client.project)
            select_query = f"SELECT config FROM `{project_id_bq}.highlight_reel_analytics.jobs` WHERE job_id = @job_id LIMIT 1"
            job_config_select = bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("job_id", "STRING", job_id)]
            )
            results = list(bq_client.query(select_query, job_config=job_config_select).result())
            if results and results[0].config:
                cfg = results[0].config
                if isinstance(cfg, str):
                    cfg = json.loads(cfg)
                cfg["final_script"] = final_script
                cfg["last_good_stage"] = "REVIEWING_SCRIPT"
                
                update_query = f"UPDATE `{project_id_bq}.highlight_reel_analytics.jobs` SET config = PARSE_JSON(@config) WHERE job_id = @job_id"
                job_config_update = bigquery.QueryJobConfig(
                    query_parameters=[
                        bigquery.ScalarQueryParameter("config", "STRING", json.dumps(cfg)),
                        bigquery.ScalarQueryParameter("job_id", "STRING", job_id)
                    ]
                )
                bq_client.query(update_query, job_config=job_config_update).result()
        except Exception as stage_err:
            logger.warning(f"Failed to persist producer stage state: {stage_err}")

        publisher = pubsub_v1.PublisherClient()
        project_id = os.environ.get("PROJECT_ID")
        topic_path = publisher.topic_path(project_id, "generate-audio")
        
        # Merge the final script back into the original payload structure expected by audio-gen
        next_payload = original_payload.copy()
        next_payload["jobId"] = job_id
        next_payload["script"] = final_script
        
        data = json.dumps(next_payload).encode("utf-8")
        publisher.publish(topic_path, data)
        logger.info(f"Job {job_id}: Successfully reviewed script and published to generate-audio topic")
    except Exception as e:
        logger.error(f"Job {job_id}: Failed to publish to next stage: {e}", exc_info=True)
        raise e
