"""End-to-end integration tests for MCP server."""

import pytest
import respx
import httpx
from unittest.mock import patch, MagicMock
from typing import Dict, Any

from learnmcp_xapi.config import Config


class TestMCPIntegration:
    """Test end-to-end MCP server functionality."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration for integration tests."""
        with patch('learnmcp_xapi.main.config') as mock_config:
            mock_config.LRS_ENDPOINT = "https://test-lrs.example.com"
            mock_config.LRS_KEY = "test_key"
            mock_config.LRS_SECRET = "test_secret"
            mock_config.ACTOR_UUID = "123e4567-e89b-12d3-a456-426614174000"
            yield mock_config
    
    @respx.mock
    async def test_record_xapi_statement_integration(self, mock_config):
        """Test complete statement recording flow."""
        # Mock LRS response
        respx.post("https://test-lrs.example.com/statements").respond(
            201, json={"id": "test-statement-id"}
        )
        
        # Import after config is mocked
        with patch('learnmcp_xapi.main.config', mock_config):
            from learnmcp_xapi.main import record_xapi_statement
        
        result = await record_xapi_statement(
            verb="practiced",
            object_id="https://example.com/activity/math/algebra",
            level=2,
            extras={"comment": "Solved quadratic equations"}
        )
        
        assert result["id"] == "test-statement-id"
        
        # Verify the request was made correctly
        request = respx.calls[0].request
        assert request.method == "POST"
        assert "statements" in str(request.url)
        
        # Parse the sent statement
        import json
        statement = json.loads(request.content.decode())
        
        # Verify statement structure
        assert statement["actor"]["account"]["name"] == "123e4567-e89b-12d3-a456-426614174000"
        assert statement["verb"]["id"] == "http://adlnet.gov/expapi/verbs/practiced"
        assert statement["object"]["id"] == "https://example.com/activity/math/algebra"
        assert statement["result"]["score"]["raw"] == 2
        assert statement["result"]["score"]["max"] == 3
        assert "comment" in statement["result"]["extensions"]["https://learnmcp.example.com/extensions/comment"]
    
    @respx.mock
    async def test_get_xapi_statements_integration(self, mock_config):
        """Test complete statements retrieval flow."""
        # Mock LRS response
        mock_statements = {
            "statements": [
                {
                    "id": "stmt-1",
                    "actor": {
                        "account": {
                            "homePage": "urn:learnmcp",
                            "name": "123e4567-e89b-12d3-a456-426614174000"
                        }
                    },
                    "verb": {
                        "id": "http://adlnet.gov/expapi/verbs/achieved",
                        "display": {"en-US": "achieved"}
                    },
                    "object": {
                        "id": "https://example.com/activity/test",
                        "objectType": "Activity"
                    },
                    "timestamp": "2023-05-22T14:30:00Z"
                }
            ]
        }
        
        respx.get("https://test-lrs.example.com/statements").respond(
            200, json=mock_statements
        )
        
        # Test the MCP tool directly
        from learnmcp_xapi.main import get_xapi_statements
        
        result = await get_xapi_statements(
            verb="achieved",
            object_id="https://example.com/activity/test",
            limit=10
        )
        
        assert len(result) == 1
        assert result[0]["id"] == "stmt-1"
        
        # Verify the request was made correctly
        request = respx.calls[0].request
        assert request.method == "GET"
        assert "statements" in str(request.url)
        assert "agent=123e4567-e89b-12d3-a456-426614174000" in str(request.url)
        assert "verb=http://adlnet.gov/expapi/verbs/achieved" in str(request.url)
        assert "activity=https://example.com/activity/test" in str(request.url)
        assert "limit=10" in str(request.url)
    
    async def test_list_available_verbs_integration(self, mock_config):
        """Test verb listing functionality."""
        from learnmcp_xapi.main import list_available_verbs
        
        result = await list_available_verbs()
        
        assert isinstance(result, dict)
        assert len(result) == 4
        assert result["experienced"] == "http://adlnet.gov/expapi/verbs/experienced"
        assert result["practiced"] == "http://adlnet.gov/expapi/verbs/practiced"
        assert result["achieved"] == "http://adlnet.gov/expapi/verbs/achieved"
        assert result["mastered"] == "http://adlnet.gov/expapi/verbs/mastered"
    
    @respx.mock
    async def test_record_statement_with_validation_error(self, mock_config):
        """Test integration with validation errors."""
        from learnmcp_xapi.main import record_xapi_statement
        
        # Should raise exception for unknown verb
        with pytest.raises(Exception) as exc_info:
            await record_xapi_statement(
                verb="unknown_verb",
                object_id="https://example.com/activity/test"
            )
        
        # Verify error message contains verb information
        assert "Unknown verb" in str(exc_info.value)
    
    @respx.mock
    async def test_record_statement_with_lrs_retry(self, mock_config):
        """Test integration with LRS retry logic."""
        # First request fails, second succeeds
        respx.post("https://test-lrs.example.com/statements").mock(
            side_effect=[
                httpx.Response(500, json={"error": "server error"}),
                httpx.Response(201, json={"id": "test-statement-id"})
            ]
        )
        
        from learnmcp_xapi.main import record_xapi_statement
        
        result = await record_xapi_statement(
            verb="mastered",
            object_id="https://example.com/course/python-basics",
            level=3
        )
        
        assert result["id"] == "test-statement-id"
        
        # Verify retry occurred (2 requests made)
        assert len(respx.calls) == 2
    
    @respx.mock
    async def test_full_learning_scenario(self, mock_config):
        """Test complete learning scenario with multiple statements."""
        # Mock multiple LRS responses
        statement_responses = [
            {"id": "stmt-practiced-1"},
            {"id": "stmt-practiced-2"}, 
            {"id": "stmt-achieved-1"}
        ]
        
        for response in statement_responses:
            respx.post("https://test-lrs.example.com/statements").respond(
                201, json=response
            )
        
        # Mock statements retrieval
        respx.get("https://test-lrs.example.com/statements").respond(
            200, json={"statements": [{"id": stmt["id"]} for stmt in statement_responses]}
        )
        
        from learnmcp_xapi.main import record_xapi_statement, get_xapi_statements
        
        # Simulate learning progression
        activity_id = "https://example.com/course/data-structures"
        
        # 1. Student practices the activity twice
        result1 = await record_xapi_statement(
            verb="practiced",
            object_id=activity_id,
            level=1,
            extras={"session": "morning"}
        )
        
        result2 = await record_xapi_statement(
            verb="practiced", 
            object_id=activity_id,
            level=2,
            extras={"session": "afternoon"}
        )
        
        # 2. Student achieves mastery
        result3 = await record_xapi_statement(
            verb="achieved",
            object_id=activity_id,
            level=3,
            extras={"final_score": 95}
        )
        
        # 3. Retrieve learning history
        history = await get_xapi_statements(
            object_id=activity_id,
            limit=10
        )
        
        # Verify the complete flow
        assert result1["id"] == "stmt-practiced-1"
        assert result2["id"] == "stmt-practiced-2" 
        assert result3["id"] == "stmt-achieved-1"
        assert len(history) == 3
        
        # Verify correct number of requests made
        assert len(respx.calls) == 4  # 3 POST + 1 GET
    
    @respx.mock
    async def test_error_handling_integration(self, mock_config):
        """Test error handling across the integration."""
        from learnmcp_xapi.main import record_xapi_statement, get_xapi_statements
        
        # Test various error scenarios
        
        # 1. Invalid object IRI
        with pytest.raises(Exception) as exc_info:
            await record_xapi_statement(
                verb="practiced",
                object_id="not-a-valid-iri"
            )
        assert "valid IRI" in str(exc_info.value)
        
        # 2. Invalid level
        with pytest.raises(Exception) as exc_info:
            await record_xapi_statement(
                verb="practiced",
                object_id="https://example.com/activity/test",
                level=5  # Should be 0-3 for integers
            )
        assert "between 0 and 3" in str(exc_info.value)
        
        # 3. LRS completely unavailable
        respx.post("https://test-lrs.example.com/statements").respond(503)
        respx.get("https://test-lrs.example.com/statements").respond(503)
        
        with pytest.raises(Exception):
            await record_xapi_statement(
                verb="practiced",
                object_id="https://example.com/activity/test"
            )
        
        with pytest.raises(Exception):
            await get_xapi_statements()


class TestConfigurationIntegration:
    """Test configuration integration with different environments."""
    
    def test_production_environment_validation(self):
        """Test that production environment enforces security requirements."""
        import os
        from unittest.mock import patch
        
        # Production config should require HTTPS
        env_vars = {
            "LRS_ENDPOINT": "http://example.com/xapi",  # HTTP not allowed
            "LRS_KEY": "test_key",
            "LRS_SECRET": "test_secret",
            "ACTOR_UUID": "123e4567-e89b-12d3-a456-426614174000",
            "ENVIRONMENT": "production"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ValueError, match="Production environment requires HTTPS"):
                Config()
    
    def test_development_environment_flexibility(self):
        """Test that development environment allows HTTP."""
        import os
        from unittest.mock import patch
        
        env_vars = {
            "LRS_ENDPOINT": "http://localhost:8080/xapi",  # HTTP allowed in dev
            "LRS_KEY": "test_key",
            "LRS_SECRET": "test_secret",
            "ACTOR_UUID": "123e4567-e89b-12d3-a456-426614174000",
            "ENVIRONMENT": "development"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = Config()  # Should not raise exception
            assert config.LRS_ENDPOINT == "http://localhost:8080/xapi"