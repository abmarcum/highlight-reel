import os
from google import genai
from google.auth import default, transport

credentials, project = default()
auth_req = transport.requests.Request()
credentials.refresh(auth_req)

try:
    client = genai.Client(
        vertexai=True, 
        project=os.environ.get("PROJECT_ID") or project, 
        location="us-central1"
    )
    response = client.models.generate_content(
        model='gemini-1.5-pro-001',
        contents='hello'
    )
    print("Success:", response.text)
except Exception as e:
    print(f"Error: {e}")
