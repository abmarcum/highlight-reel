# Project Plan: Automated Highlight Reel Enterprise Application

This document outlines the architecture, infrastructure, and implementation phases for the automated sports highlight reel web application.

## 1. Architecture Overview

The system is designed as an event-driven, enterprise-grade pipeline using Google Cloud Platform (GCP) serverless components.

*   **Frontend**: Vite + React (JavaScript), styled with modern, premium vanilla CSS aesthetics.
*   **Authentication**: Google Cloud Identity Platform (or Firebase Auth) for passwordless OAuth (e.g., Google Sign-In).
*   **Hosting**: Google Cloud Run (containerized frontend/BFF).
*   **Networking**: Global HTTP(S) Load Balancer with Google-managed SSL Certificates.
*   **Storage**: Google Cloud Storage (GCS) for raw videos, configs, assets (logos, music, bumpers), and final reels.
*   **Eventing/Messaging**: Google Cloud Pub/Sub to decouple processing stages (Analysis, Audio, Render, Publish).
*   **Compute (Backend)**: Google Cloud Functions (Python 3.11+) triggered by GCS and Pub/Sub.
*   **AI/ML**: Vertex AI (Gemini Multimodal) for spatial/temporal video analysis and script generation. Google Cloud Text-to-Speech (TTS) for commentary.
*   **Database/Analytics**: Google BigQuery to store job metadata, configurations, pipeline states, and **Cost/Token Usage Analytics**.

## 2. Infrastructure as Code (Terraform)

Modular Terraform setup:
*   **`main.tf`**, **`storage.tf`**, **`run.tf`**, **`lb.tf`**, **`iam.tf`**
*   **`pubsub.tf`**: Topics (`job-created`, `analyze-video`, `generate-audio`, `render-video`, `publish-video`).
*   **`functions.tf`**: Deployments for the 5 core pipeline functions.
*   **`bigquery.tf`**: Schema for job statuses and API billing/token usage metrics.

## 3. Video Processing Pipeline (Python)

The backend pipeline relies on asynchronous Python Cloud Functions communicating via Pub/Sub.

1.  **Ingestion & Initialization (GCS Triggered Function)**
    *   Triggered by file uploads to `raw-videos`.
    *   Reads `.job` configuration, which now supports: **Tone, Dual Voices, Background Music, Branding Watermark, Intro/Outro Bumpers, Aspect Ratio (e.g., 9:16), Team/Player Bias, Auto-Publish Destinations, and Webhook URLs.**
    *   Inserts record to BigQuery (`PENDING`) and publishes to `analyze-video`.

### 3.1 The `.job` File Schema
The `.job` file is a JSON payload uploaded alongside the raw video. It perfectly mirrors the UI job submission form, enabling 100% automated workflows.

```json
{
  "language": "es",
  "duration": 60,
  "tone": "sportscast", 
  "commentarySetup": "dual",
  "personas": ["en-US-Journey-D", "en-US-Journey-F"],
  "musicTrack": "gs://assets-bucket/music/upbeat_electronic.mp3",
  "brandingLogo": "gs://assets-bucket/logos/my_brand.png",
  "introBumper": "gs://assets-bucket/bumpers/intro.mp4",
  "outroBumper": "gs://assets-bucket/bumpers/outro.mp4",
  "aspectRatio": "9:16",
  "teamPlayerBias": "Focus heavily on the plays made by player #12.",
  "subtitlesEnabled": true,
  "autoPublish": ["youtube", "twitter"],
  "webhookUrls": ["https://hooks.slack.com/services/"]
}
```
2.  **Video Analysis (Pub/Sub Triggered Function)**
    *   **Frame Extraction & CLIP Embeddings**: Extracts frames from the video and generates vector embeddings using a CLIP model (Contrastive Language-Image Pretraining).
    *   **Reciprocal Rank Fusion (RRF)**: Combines semantic search rankings (cosine similarity of text queries like the **Team/Player Bias** against the CLIP frame embeddings) with Gemini 3.1 Pro's native timestamp extraction to pinpoint the absolute best highlights.
    *   Generates commentary script and a **Social Media Description (Tweet/Caption)** using Gemini 3.1 Pro.
    *   If **9:16 Cropping** is requested, Vertex AI identifies spatial bounding boxes to track the action (pan-and-scan).
    *   Publishes to `generate-audio`.
3.  **Commentary & Subtitle Generation (Pub/Sub Triggered Function)**
    *   Uses Google TTS to generate single or dual-personality commentary.
    *   Creates a **Subtitles/Closed Captions (.srt / .vtt)** file synchronized with the generated audio.
    *   Publishes to `render-video`.
4.  **Video Rendering (Dedicated Cloud Run Job)**
    *   Executed as a Cloud Run Job (triggered via Pub/Sub) to handle long-running, CPU/Memory intensive video encoding without timeout constraints.
    *   Uses advanced `ffmpeg` scripting to:
        *   Trim highlights and apply **Multi-Clip Transitions** (crossfades/wipes).
        *   Apply **9:16 Pan-and-Scan Cropping** based on Vertex AI bounding boxes.
        *   Mix **Background Music** with **Audio Ducking** (lowering music volume when commentary speaks).
        *   Overlay the **Custom Branding/Watermark**.
        *   Burn in the dynamic **Subtitles**.
        *   Prepend and append the **Intro/Outro Bumpers**.
    *   Uploads `.mp4` to `processed-highlights` and publishes to `publish-video`.
5.  **Publishing & Notifications (Pub/Sub Triggered Function) [NEW]**
    *   Subscribes to `publish-video`.
    *   **Auto-Publishing**: Pushes the video and generated description directly to YouTube, Twitter, or Instagram via APIs if configured.
    *   **Live Notifications**: Fires webhooks to Slack, Discord, or Email to alert the team that the job is complete.
    *   Logs final **Vertex AI Token Usage and TTS Costs** to BigQuery.

## 4. Frontend Application (Vite + React)

*   **Authentication**: Passwordless OAuth login.
*   **Video Library**: View original videos alongside finished reels.
*   **Pipeline Management & Job Configuration**: Form to set all new parameters:
    *   Language, Tone, Single/Dual Personas.
    *   **Music Selection & Branding**: Upload logos or select background tracks.
    *   **Social & Layout**: Toggle 9:16 Cropping, enter Team/Player Bias prompts, enable Subtitles, and link Social Media accounts for auto-publishing.
    *   **Notifications**: Input webhook URLs for Slack/Discord.
*   **Analytics Dashboard [NEW]**: Displays **Cost & Token Tracking**, calculating Vertex AI and TTS API usage per job to monitor platform ROI.

### Containerization (Dockerfile) & Artifact Registry
*(Maintained from previous version: Multi-stage Docker build with Node & Nginx, deployed to Cloud Run via Artifact Registry).*

## 5. Execution Plan

*   **Phase 1: Infrastructure**: Terraform for GCS, BigQuery, Pub/Sub, Load Balancers, and Auth.
*   **Phase 2: Core AI & Audio**: Vertex AI analysis (including Bias/Cropping) and TTS (+ Subtitles).
*   **Phase 3: Advanced Rendering**: Complex `ffmpeg` pipelines for transitions, ducking, bumpers, and watermarks.
*   **Phase 4: Publishing & Integrations**: Auto-publishing APIs, webhooks, and BigQuery cost logging.
*   **Phase 5: Frontend Development**: Vite UI with advanced configuration forms and Analytics Dashboard.
*   **Phase 6: Integration & Polish**: E2E testing of the massive feature set.
