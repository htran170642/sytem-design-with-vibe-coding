"""
Tests for Health Check Endpoints
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    """Test basic health check endpoint"""
    response = client.get("/health")
    
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app_name"] == "AIVA"
    assert "version" in data
    assert "environment" in data
    assert "uptime_seconds" in data
    assert data["uptime_seconds"] >= 0


def test_detailed_health_check():
    """Test detailed health check endpoint"""
    response = client.get("/health/detailed")
    
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "healthy"
    assert "components" in data
    
    # Check components
    components = data["components"]
    assert "application" in components
    assert "configuration" in components
    assert "features" in components
    
    # Check application component
    assert components["application"]["status"] == "healthy"
    assert components["application"]["uptime_seconds"] >= 0
    
    # Check configuration component
    assert components["configuration"]["status"] == "healthy"
    assert "debug_mode" in components["configuration"]
    assert "log_level" in components["configuration"]
    
    # Check features component
    assert components["features"]["status"] == "healthy"
    assert "docs_enabled" in components["features"]
    assert "rag_enabled" in components["features"]


def test_readiness_check():
    """Test Kubernetes readiness probe endpoint"""
    response = client.get("/health/ready")
    
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "ready"
    assert "message" in data


def test_liveness_check():
    """Test Kubernetes liveness probe endpoint"""
    response = client.get("/health/live")
    
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "alive"
    assert "message" in data


def test_root_endpoint():
    """Test root endpoint"""
    response = client.get("/")
    
    assert response.status_code == 200
    
    data = response.json()
    assert data["name"] == "AIVA"
    assert "version" in data
    assert "environment" in data
    assert data["status"] == "running"
    assert "docs_url" in data


def test_health_response_structure():
    """Test that health response has expected structure"""
    response = client.get("/health")
    data = response.json()
    
    # Required fields
    required_fields = ["status", "app_name", "version", "environment", "uptime_seconds"]
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"


def test_detailed_health_components():
    """Test that all expected components are present"""
    response = client.get("/health/detailed")
    data = response.json()
    
    components = data["components"]
    expected_components = ["application", "configuration", "features"]
    
    for component in expected_components:
        assert component in components, f"Missing component: {component}"
        assert "status" in components[component]