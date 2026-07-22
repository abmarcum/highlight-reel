import json
import pytest
from unittest.mock import patch, MagicMock

# Set env vars before importing to prevent BigQuery client initialization errors
import os
os.environ["PROJECT_ID"] = "test-project"

# Import the module to test
from api import main

@pytest.fixture
def mock_bq_client():
    with patch('api.main.bq_client') as mock:
        yield mock

@pytest.fixture
def mock_storage_client():
    with patch('api.main.storage_client') as mock:
        yield mock

def create_mock_request(method, path, headers=None, json_data=None):
    request = MagicMock()
    request.method = method
    request.path = path
    request.headers = headers or {}
    
    # Define get_json behavior
    def get_json():
        return json_data
    request.get_json = get_json
    
    return request

def test_cors_preflight():
    request = create_mock_request("OPTIONS", "/")
    response = main.get_jobs(request)
    assert response[1] == 204
    assert "Access-Control-Allow-Origin" in response[2]

@patch('api.main.get_user_identity')
def test_get_jobs_viewer_can_list(mock_identity, mock_bq_client):
    mock_identity.return_value = ("viewer@example.com", "viewer")
    
    # Mock BigQuery results for list
    mock_query_job = MagicMock()
    mock_query_job.result.return_value = []
    mock_bq_client.query.return_value = mock_query_job
    
    request = create_mock_request("GET", "/")
    response = main.get_jobs(request)
    
    assert response[1] == 200
    res_data = json.loads(response[0].get_data(as_text=True))
    assert "jobs" in res_data

@patch('api.main.get_user_identity')
def test_delete_job_admin_allowed(mock_identity, mock_bq_client):
    mock_identity.return_value = ("admin@example.com", "admin")
    
    request = create_mock_request("DELETE", "/job-123")
    response = main.get_jobs(request)
    
    assert response[1] == 200
    res_data = json.loads(response[0].get_data(as_text=True))
    assert res_data["message"] == "Job deleted"
    mock_bq_client.query.assert_called()

@patch('api.main.get_user_identity')
def test_delete_job_viewer_forbidden(mock_identity):
    mock_identity.return_value = ("viewer@example.com", "viewer")
    
    request = create_mock_request("DELETE", "/job-123")
    response = main.get_jobs(request)
    
    assert response[1] == 403
    res_data = json.loads(response[0].get_data(as_text=True))
    assert "Forbidden" in res_data["error"]

@patch('api.main.get_user_identity')
def test_submit_job_viewer_forbidden(mock_identity):
    mock_identity.return_value = ("viewer@example.com", "viewer")
    
    request = create_mock_request("POST", "/", json_data={"tone": "hype"})
    response = main.get_jobs(request)
    
    assert response[1] == 403

@patch('api.main.get_user_identity')
def test_restart_job_admin_allowed(mock_identity, mock_bq_client, mock_storage_client):
    mock_identity.return_value = ("admin@example.com", "admin")
    
    # Mock BigQuery fetch for config
    mock_query_job = MagicMock()
    mock_row = MagicMock()
    mock_row.config = '{"tone": "hype"}'
    mock_query_job.result.return_value = [mock_row]
    mock_bq_client.query.return_value = mock_query_job
    
    request = create_mock_request("POST", "/job-123/restart")
    response = main.get_jobs(request)
    
    assert response[1] == 200
    res_data = json.loads(response[0].get_data(as_text=True))
    assert res_data["message"] == "Job restarted"
