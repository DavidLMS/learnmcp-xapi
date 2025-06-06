"""Tests for MCP core functionality with plugin system."""

import pytest
import respx
import httpx
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timezone

from learnmcp_xapi.mcp.core import (
    record_statement, 
    get_statements,
    _build_score
)
from fastapi import HTTPException


class TestBuildScore:
    """Test score building functionality."""
    
    def test_build_score_integer_level(self):
        """Test score building with integer level (0-3)."""
        score = _build_score(2, {})
        
        assert score["raw"] == 2
        assert score["min"] == 0
        assert score["max"] == 3
    
    def test_build_score_float_level(self):
        """Test score building with float level (0-100)."""
        score = _build_score(85.5, {})
        
        assert score["raw"] == 85.5
        assert score["min"] == 0
        assert score["max"] == 100
    
    def test_build_score_with_custom_max(self):
        """Test score building with custom max from extras."""
        score = _build_score(45.0, {"score_max": 50})
        
        assert score["raw"] == 45.0
        assert score["min"] == 0
        assert score["max"] == 50
    
    def test_build_score_invalid_integer_level(self):
        """Test score building with invalid integer level (treated as float)."""
        # Values outside 0-3 are treated as float scores
        score = _build_score(4, {})
        assert score["raw"] == 4.0
        assert score["max"] == 100  # Default float max
        
        score = _build_score(-1, {})
        assert score["raw"] == -1.0
        assert score["max"] == 100
    
    def test_build_score_float_level_no_validation(self):
        """Test score building with float level (no bounds validation)."""
        # Current implementation doesn't validate bounds
        score = _build_score(-5.0, {})
        assert score["raw"] == -5.0
        assert score["max"] == 100
        
        score = _build_score(150.0, {})
        assert score["raw"] == 150.0
        assert score["max"] == 100
    
    def test_build_score_custom_max_no_validation(self):
        """Test score building with custom max (no validation)."""
        # Current implementation doesn't validate score_max
        score = _build_score(50.0, {"score_max": -10})
        assert score["raw"] == 50.0
        assert score["max"] == -10.0
        
        score = _build_score(50.0, {"score_max": 40})
        assert score["raw"] == 50.0
        assert score["max"] == 40.0


class TestRecordStatement:
    """Test statement recording functionality."""
    
    @respx.mock
    async def test_record_statement_success(self):
        """Test successful statement recording."""
        respx.post(f"https://test-lrs.com/statements").respond(
            201, json={"id": "test-statement-id"}
        )
        
        with patch('learnmcp_xapi.mcp.core.get_lrs_plugin') as mock_get_plugin:
            mock_plugin = AsyncMock()
            mock_plugin.post_statement.return_value = {"id": "test-statement-id"}
            mock_get_plugin.return_value = mock_plugin
            
            result = await record_statement(
                actor_uuid="123e4567-e89b-12d3-a456-426614174000",
                verb="practiced",
                object_id="https://example.com/activity/1",
                level=2
            )
            
            assert result["id"] == "test-statement-id"
            mock_plugin.post_statement.assert_called_once()
    
    async def test_record_statement_unknown_verb(self):
        """Test statement recording fails for unknown verb."""
        with pytest.raises(HTTPException) as exc_info:
            await record_statement(
                actor_uuid="123e4567-e89b-12d3-a456-426614174000",
                verb="unknown_verb",
                object_id="https://example.com/activity/1"
            )
        
        assert exc_info.value.status_code == 400
        assert "Unknown verb" in str(exc_info.value.detail)
    
    async def test_record_statement_invalid_object_id(self):
        """Test statement recording fails for invalid object ID."""
        with pytest.raises(HTTPException) as exc_info:
            await record_statement(
                actor_uuid="123e4567-e89b-12d3-a456-426614174000",
                verb="practiced",
                object_id="not-a-valid-iri"
            )
        
        assert exc_info.value.status_code == 400
        assert "must be a valid IRI" in str(exc_info.value.detail)
    
    @patch('learnmcp_xapi.mcp.core.validate_xapi_statement')
    async def test_record_statement_validation_error(self, mock_validate):
        """Test statement recording fails for validation errors."""
        from jsonschema import ValidationError
        
        mock_validate.side_effect = ValidationError("Required field missing")
        
        with pytest.raises(HTTPException) as exc_info:
            await record_statement(
                actor_uuid="123e4567-e89b-12d3-a456-426614174000",
                verb="practiced",
                object_id="https://example.com/activity/1"
            )
        
        assert exc_info.value.status_code == 400
        assert "Invalid xAPI statement" in str(exc_info.value.detail)
    
    @respx.mock
    async def test_record_statement_with_extras(self):
        """Test statement recording with extras."""
        respx.post(f"https://test-lrs.com/statements").respond(
            201, json={"id": "test-statement-id"}
        )
        
        with patch('learnmcp_xapi.mcp.core.get_lrs_plugin') as mock_get_plugin:
            mock_plugin = AsyncMock()
            mock_plugin.post_statement.return_value = {"id": "test-statement-id"}
            mock_get_plugin.return_value = mock_plugin
            
            extras = {
                "comment": "Great work!",
                "duration": "PT5M",
                "score_max": 5
            }
            
            result = await record_statement(
                actor_uuid="123e4567-e89b-12d3-a456-426614174000",
                verb="achieved",
                object_id="https://example.com/activity/1",
                level=4.5,
                extras=extras
            )
            
            # Verify the statement was built correctly
            call_args = mock_plugin.post_statement.call_args[0][0]
            assert "result" in call_args
            assert "extensions" in call_args["result"]
            assert call_args["result"]["score"]["max"] == 5
            assert call_args["result"]["score"]["raw"] == 4.5
    
    @respx.mock 
    async def test_record_statement_complete_structure(self):
        """Test that recorded statements have complete xAPI structure."""
        with patch('learnmcp_xapi.mcp.core.get_lrs_plugin') as mock_get_plugin:
            mock_plugin = AsyncMock()
            mock_plugin.post_statement.return_value = {"id": "test-id"}
            mock_get_plugin.return_value = mock_plugin
            
            await record_statement(
                actor_uuid="123e4567-e89b-12d3-a456-426614174000",
                verb="experienced",
                object_id="https://example.com/activity/test"
            )
            
            statement = mock_plugin.post_statement.call_args[0][0]
            
            # Verify complete xAPI structure
            assert "actor" in statement
            assert statement["actor"]["account"]["homePage"] == "https://learnmcp.example.com"
            assert statement["actor"]["account"]["name"] == "123e4567-e89b-12d3-a456-426614174000"
            
            assert "verb" in statement
            assert statement["verb"]["id"] == "http://adlnet.gov/expapi/verbs/experienced"
            assert statement["verb"]["display"]["en-US"] == "experienced"
            
            assert "object" in statement
            assert statement["object"]["id"] == "https://example.com/activity/test"
            assert statement["object"]["objectType"] == "Activity"
            
            assert "context" in statement
            assert statement["context"]["platform"] == "learnmcp-xapi"
            
            assert "timestamp" in statement
            # Verify timestamp is recent (within last minute)
            timestamp = datetime.fromisoformat(statement["timestamp"].replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            assert (now - timestamp).total_seconds() < 60


class TestGetStatements:
    """Test statements retrieval functionality."""
    
    @respx.mock
    async def test_get_statements_success(self):
        """Test successful statements retrieval."""
        mock_statements = [
            {
                "id": "stmt1",
                "actor": {"account": {"name": "test-uuid"}},
                "verb": {"id": "http://adlnet.gov/expapi/verbs/experienced"},
                "object": {"id": "https://example.com/activity/1"}
            }
        ]
        
        with patch('learnmcp_xapi.mcp.core.get_lrs_plugin') as mock_get_plugin:
            mock_plugin = AsyncMock()
            mock_plugin.get_statements.return_value = mock_statements
            mock_get_plugin.return_value = mock_plugin
            
            result = await get_statements(
                actor_uuid="test-uuid"
            )
            
            assert result == mock_statements
            mock_plugin.get_statements.assert_called_once_with(
                actor_uuid="test-uuid",
                verb=None,
                object_id=None,
                since=None,
                until=None,
                limit=50
            )
    
    @respx.mock
    async def test_get_statements_with_filters(self):
        """Test statements retrieval with filters."""
        with patch('learnmcp_xapi.mcp.core.get_lrs_plugin') as mock_get_plugin:
            mock_plugin = AsyncMock()
            mock_plugin.get_statements.return_value = []
            mock_get_plugin.return_value = mock_plugin
            
            await get_statements(
                actor_uuid="test-uuid",
                verb="practiced",
                object_id="https://example.com/activity/1",
                since="2023-01-01T00:00:00Z",
                until="2023-12-31T23:59:59Z",
                limit=50
            )
            
            # Verify the call was made with correct parameters
            call_args = mock_plugin.get_statements.call_args
            assert call_args[1]["actor_uuid"] == "test-uuid"
            assert call_args[1]["verb"] == "http://adlnet.gov/expapi/verbs/practiced"
            assert call_args[1]["object_id"] == "https://example.com/activity/1"
            assert call_args[1]["limit"] == 50
            # since and until should be datetime objects
            assert call_args[1]["since"] is not None
            assert call_args[1]["until"] is not None
    
    async def test_get_statements_unknown_verb(self):
        """Test statements retrieval fails for unknown verb."""
        with pytest.raises(HTTPException) as exc_info:
            await get_statements(
                actor_uuid="test-uuid",
                verb="unknown_verb"
            )
        
        assert exc_info.value.status_code == 400
        assert "Unknown verb" in str(exc_info.value.detail)
    
    async def test_get_statements_invalid_since_datetime(self):
        """Test statements retrieval fails for invalid since datetime."""
        with pytest.raises(HTTPException) as exc_info:
            await get_statements(
                actor_uuid="test-uuid",
                since="not-a-datetime"
            )
        
        assert exc_info.value.status_code == 400
        assert "Invalid since datetime format" in str(exc_info.value.detail)
    
    async def test_get_statements_invalid_until_datetime(self):
        """Test statements retrieval fails for invalid until datetime."""
        with pytest.raises(HTTPException) as exc_info:
            await get_statements(
                actor_uuid="test-uuid",
                until="not-a-datetime"
            )
        
        assert exc_info.value.status_code == 400
        assert "Invalid until datetime format" in str(exc_info.value.detail)
    
    async def test_get_statements_limit_enforced(self):
        """Test that statement limit is enforced."""
        with patch('learnmcp_xapi.mcp.core.get_lrs_plugin') as mock_get_plugin:
            mock_plugin = AsyncMock()
            mock_plugin.get_statements.return_value = []
            mock_get_plugin.return_value = mock_plugin
            
            await get_statements(
                actor_uuid="test-uuid",
                limit=100  # Higher than max
            )
            
            # Verify limit was capped at 50
            call_args = mock_plugin.get_statements.call_args
            assert call_args[1]["limit"] == 50
    
    @respx.mock
    async def test_get_statements_plugin_error(self):
        """Test statements retrieval handles plugin errors."""
        with patch('learnmcp_xapi.mcp.core.get_lrs_plugin') as mock_get_plugin:
            mock_plugin = AsyncMock()
            mock_plugin.get_statements.side_effect = HTTPException(
                status_code=503,
                detail="LRS unavailable"
            )
            mock_get_plugin.return_value = mock_plugin
            
            with pytest.raises(HTTPException) as exc_info:
                await get_statements(actor_uuid="test-uuid")
            
            assert exc_info.value.status_code == 503


class TestPluginIntegration:
    """Test integration with plugin system."""
    
    @patch('learnmcp_xapi.mcp.core.PluginFactory')
    @patch('learnmcp_xapi.mcp.core.config')
    def test_get_lrs_plugin_creation(self, mock_config, mock_factory):
        """Test LRS plugin creation and caching."""
        from learnmcp_xapi.mcp.core import get_lrs_plugin, _lrs_plugin
        
        # Reset global plugin instance
        import learnmcp_xapi.mcp.core as core_module
        core_module._lrs_plugin = None
        
        mock_plugin = AsyncMock()
        mock_factory.create_from_config.return_value = mock_plugin
        
        # First call should create plugin
        result1 = get_lrs_plugin()
        assert result1 == mock_plugin
        mock_factory.create_from_config.assert_called_once_with(mock_config)
        
        # Second call should return cached plugin
        result2 = get_lrs_plugin()
        assert result2 == mock_plugin
        # Factory should still only be called once
        assert mock_factory.create_from_config.call_count == 1
    
    async def test_record_statement_uses_plugin_system(self):
        """Test that record_statement uses the plugin system correctly."""
        with patch('learnmcp_xapi.mcp.core.get_lrs_plugin') as mock_get_plugin:
            mock_plugin = AsyncMock()
            mock_plugin.post_statement.return_value = {"id": "test-id", "stored": True}
            mock_get_plugin.return_value = mock_plugin
            
            result = await record_statement(
                actor_uuid="test-uuid",
                verb="experienced",
                object_id="https://example.com/activity/1"
            )
            
            # Verify plugin was called
            assert mock_get_plugin.called
            assert mock_plugin.post_statement.called
            assert result["id"] == "test-id"
    
    async def test_get_statements_uses_plugin_system(self):
        """Test that get_statements uses the plugin system correctly."""
        mock_statements = [{"id": "stmt1"}]
        
        with patch('learnmcp_xapi.mcp.core.get_lrs_plugin') as mock_get_plugin:
            mock_plugin = AsyncMock()
            mock_plugin.get_statements.return_value = mock_statements
            mock_get_plugin.return_value = mock_plugin
            
            result = await get_statements(actor_uuid="test-uuid")
            
            # Verify plugin was called
            assert mock_get_plugin.called
            assert mock_plugin.get_statements.called
            assert result == mock_statements