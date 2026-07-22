# Highlight Reel Enterprise - Infrastructure as Code

This directory contains the **Terraform** configurations defining the entire Google Cloud serverless architecture for the application.

## Core Principles
*   **Least Privilege**: Strict IAM rules limit what each Cloud Function and Cloud Run Job can access (e.g., the `audio_gen` service cannot write to BigQuery).
*   **Event-Driven**: Complete reliance on Eventarc and Pub/Sub to orchestrate workflows without long-polling or tight coupling.
*   **Cost-Optimized**: Serverless architecture ensures compute is only billed when highlight reels are actively processing.

## Resource Layout

*   **`main.tf`**: Provider configurations and API enablement.
*   **`variables.tf`**: Project-level variables (e.g., `project_id`, `region`, `iap_domain`).
*   **`iap.tf`**: Provisions the Global External HTTPS Load Balancer, SSL Certificates, and Identity-Aware Proxy (IAP) settings.
*   **`dns.tf`**: Manages Cloud DNS records to point custom domains to the Load Balancer IP.
*   **`storage.tf`**: Defines the raw ingest bucket and the processed highlights bucket (with appropriate lifecycle rules and CORS).
*   **`pubsub.tf`**: Defines the 4 primary topics (`analyze-video`, `generate-audio`, `render-video`, `publish-video`).
*   **`iam.tf`**: Defines dedicated service accounts for each microservice and assigns exact roles (`roles/storage.objectAdmin`, `roles/aiplatform.user`, etc.).
*   **`functions.tf`**: Defines the Gen 2 Google Cloud Functions for the backend pipeline, mapping source code to the respective Pub/Sub triggers.
*   **`run.tf`**: Defines the dedicated **Cloud Run Job** for the high-intensity `ffmpeg` Video Renderer, specifying heavy CPU/Memory limits to prevent timeouts.
*   **`bigquery.tf`**: Provisions the `highlight_analytics` dataset and `job_status` tables.
*   **`secrets.tf`**: Provisions GCP Secret Manager secrets (`gemini-api-key`, `iap-client-id`, `iap-client-secret`, `iap-domain`, `slack-webhook-url`, `proxy-pass`) and manages IAM Secret Accessor permissions for application service accounts.

## Architecture Topology

```mermaid
graph TD
    %% User Interaction
    User((User))
    
    subgraph "Frontend & API"
        LB[Global Load Balancer & IAP]
        UI[Frontend UI<br/>Cloud Run]
        API[Highlight API<br/>Cloud Function]
    end

    User -->|Access UI| LB
    LB --> UI
    UI -->|Submit Job & Fetch Data| API
    
    subgraph "Storage & Databases"
        GCS_RAW[(GCS: Raw Videos)]
        GCS_OUT[(GCS: Processed)]
        BQ[(BigQuery<br/>Analytics & State)]
    end

    API -->|Generate Signed URL| GCS_RAW
    User -.->|Direct Upload via Signed URL| GCS_RAW
    API -->|Write Job State| BQ
    API -.->|Write .job config| GCS_RAW

    subgraph "Eventing (Pub/Sub)"
        PS1[Topic: analyze-video]
        PS2[Topic: review-script]
        PS3[Topic: generate-audio]
        PS4[Topic: publish-video]
    end

    subgraph "AI & Processing Pipeline"
        F1[Job Initiator<br/>Cloud Function]
        F2[Video Analyzer<br/>Cloud Function]
        F3[Job Producer<br/>Cloud Function]
        F4[Audio Generator<br/>Cloud Function]
        J1[Video Renderer<br/>Cloud Run Job]
        F5[Job Publisher<br/>Cloud Function]
    end

    GCS_RAW -- Eventarc: Object Finalized --> F1
    F1 -->|Format Job & Publish| PS1
    PS1 --> F2
    F2 <-->|Gemini 3.5 Flash Analysis| VertexAI{Vertex AI API}
    F2 -->|Publish Script| PS2
    PS2 --> F3
    F3 <-->|Gemini 3.5 Flash Review| VertexAI
    F3 -->|Publish Final Script| PS3
    PS3 --> F4
    F4 <-->|Text-to-Speech| TTS{GCP TTS API}
    F4 -->|Upload Audio/SRT| GCS_OUT
    F4 -->|Trigger Cloud Run Job API| J1
    J1 -->|Download Inputs| GCS_RAW
    J1 -->|ffmpeg Merge| GCS_OUT
    J1 -->|Publish Completion| PS4
    PS4 --> F5
    F5 -->|Update Final State| BQ

    classDef gcp fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#0d47a1;
    classDef ext fill:#fff3e0,stroke:#e65100,stroke-width:2px,color:#e65100;
    classDef storage fill:#f1f8e9,stroke:#33691e,stroke-width:2px,color:#1b5e20;
    classDef pubsub fill:#fce4ec,stroke:#880e4f,stroke-width:2px,color:#880e4f;
    
    class UI,API,F1,F2,F3,F4,J1,F5,LB gcp;
    class VertexAI,TTS ext;
    class GCS_RAW,GCS_OUT,BQ storage;
    class PS1,PS2,PS3,PS4 pubsub;
```

## Deployment

This platform strictly separates **Infrastructure Provisioning** from **Application CI/CD**. To ensure secure, least-privilege deployments, you must run Terraform locally (or via a dedicated admin pipeline) to bootstrap the environment before deploying application code.

**Instructions:**
1. Ensure you are authenticated with GCP as an administrative user (`gcloud auth application-default login`).
2. Verify your user has `Owner` or `Project IAM Admin` roles.
3. Create a `terraform.tfvars` file containing `project_id`, `gemini_api_key`, `iap_domain`, `iap_client_id`, `iap_client_secret`, `slack_webhook_url`, and `proxy_pass` (ensure `terraform.tfvars` is ignored by git).
4. Run the following commands:
```bash
terraform init
terraform plan
terraform apply
```

### Next Step: Application CI/CD

Once the Terraform execution completes successfully, the infrastructure (Buckets, IAM, Pub/Sub, etc.) is fully provisioned. However, the Cloud Run UI and the Video Renderer container still need to be built and deployed.

Navigate back to the root of the project and trigger Cloud Build:
```bash
cd ../..
export PROJECT_ID="YOUR_PROJECT_ID"
gcloud builds submit --config cloudbuild.yaml .
```
This will build your Docker containers, push them to the Artifact Registry that Terraform just created, and deploy them to Cloud Run.
