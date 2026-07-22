import datetime
from google.cloud import storage
import google.auth
from google.auth.transport import requests
from google.auth import iam

def sign():
    credentials, project = google.auth.default()
    request = requests.Request()
    credentials.refresh(request)
    email = credentials.service_account_email
    
    # Try passing email and access_token
    print("Using access token:")
    print("Email:", email)
    
    # Mock blob
    class MockBlob:
        def __init__(self):
            self.name = "test"
            self.bucket = type('Bucket', (object,), {'name': 'test', 'client': type('Client', (object,), {'_credentials': credentials})()})()
            
    client = storage.Client(credentials=credentials)
    bucket_name = f"{project}-raw-videos" if project else "raw-videos"
    blob = client.bucket(bucket_name).blob("test.mp4")
    
    try:
        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(hours=1),
            method="PUT",
            service_account_email=email,
            access_token=credentials.token
        )
        print("SUCCESS:", url[:50])
    except Exception as e:
        print("ERROR:", str(e))

sign()
