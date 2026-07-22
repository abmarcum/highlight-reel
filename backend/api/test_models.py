import google.auth
from google.cloud import aiplatform_v1
import requests
import os

try:
    credentials, project = google.auth.default()
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    token = credentials.token

    print(f"Testing with token for project: {project}")

    url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{project}/locations/us-central1/publishers/google/models/gemini-1.5-pro-001:generateContent"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "contents": [{"role": "user", "parts": [{"text": "Hello"}]}]
    }

    print("Testing gemini-1.5-pro-001...")
    response = requests.post(url, headers=headers, json=data)
    print(response.status_code)
    print(response.json())
    
    url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{project}/locations/us-central1/publishers/google/models/gemini-1.5-pro-preview-0514:generateContent"
    print("Testing gemini-1.5-pro-preview-0514...")
    response = requests.post(url, headers=headers, json=data)
    print(response.status_code)
    print(response.json())

except Exception as e:
    print(f"Error: {e}")
