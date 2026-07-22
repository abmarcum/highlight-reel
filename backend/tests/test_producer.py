import json
import base64
import pytest
from unittest.mock import patch, MagicMock
from cloudevents.http import CloudEvent

import os
os.environ["PROJECT_ID"] = "test-project"

from producer import main

@pytest.fixture
def mock_vertexai():
    with patch('producer.main.GenerativeModel') as mock:
        yield mock

@pytest.fixture
def mock_pubsub():
    with patch('producer.main.pubsub_v1.PublisherClient') as mock:
        yield mock

@pytest.fixture
def mock_bq():
    with patch('producer.main.bigquery.Client') as mock:
        yield mock

def create_cloud_event(payload):
    data = base64.b64encode(json.dumps(payload).encode('utf-8')).decode('utf-8')
    attributes = {
        "type": "google.cloud.pubsub.topic.v1.messagePublished",
        "source": "//pubsub.googleapis.com/",
    }
    event = CloudEvent(attributes, {"message": {"data": data}})
    # manually set id for testing
    event["id"] = "test-event-id"
    return event

def test_producer_missing_script(mock_bq, mock_vertexai):
    payload = {"jobId": "job-123"} # Missing script
    event = create_cloud_event(payload)
    
    # We expect it to continue since it uses script_and_timestamps (which is None)
    # But wait, GenerativeModel will be called with None in the prompt.
    # Let's mock a failure to test error writing
    mock_vertexai.side_effect = Exception("Vertex AI failed")
    
    with pytest.raises(Exception):
        main.review_script(event)
        
    mock_bq.return_value.query.assert_called()

def test_producer_successful_review(mock_vertexai, mock_pubsub, mock_bq):
    payload = {
        "jobId": "job-123",
        "script": "Draft script content",
        "original_payload": {"tone": "hype", "teamPlayerBias": "any"}
    }
    event = create_cloud_event(payload)
    
    # Mock LLM response
    mock_model_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Final polished script"
    mock_model_instance.generate_content.return_value = mock_response
    mock_vertexai.return_value = mock_model_instance
    
    # Mock Publisher
    mock_publisher_instance = MagicMock()
    mock_pubsub.return_value = mock_publisher_instance
    
    main.review_script(event)
    
    mock_model_instance.generate_content.assert_called_once()
    mock_publisher_instance.publish.assert_called_once()
    
    # Verify the published payload includes the original and the new script
    call_args = mock_publisher_instance.publish.call_args
    published_data = json.loads(call_args[0][1].decode('utf-8'))
    assert published_data["script"] == "Final polished script"
    assert published_data["jobId"] == "job-123"
    assert published_data["tone"] == "hype"
