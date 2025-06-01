"""Tests for Ralph LRS plugin."""

import pytest
import respx
import httpx
from unittest.mock import patch, AsyncMock
from datetime import datetime, timezone

from learnmcp_xapi.plugins.ralph import RalphPlugin, RalphConfig


class TestRalphPlugin:
    """Test Ralph plugin functionality, authentication, and retry logic."""
    
    @pytest.fixture
    def mock_basic_auth_config(self):
        """Mock configuration for Basic Auth testing."""
        return {
            "endpoint": "https://ralph-lrs.example.com",
            "username": "test_user",
            "password": "test_password",
            "timeout": 30,
            "retry_attempts": 3
        }
    
    @pytest.fixture
    def mock_oidc_config(self):
        """Mock configuration for OIDC testing."""
        return {
            "endpoint": "https://ralph-lrs.example.com",
            "oidc_token_url": "https://auth.example.com/oauth2/token",
            "oidc_client_id": "test_client",
            "oidc_client_secret": "test_secret",
            "timeout": 30,
            "retry_attempts": 3
        }
    
    @pytest.fixture
    def ralph_basic_auth_plugin(self, mock_basic_auth_config):
        """Create Ralph plugin instance with Basic Auth for testing."""
        return RalphPlugin(mock_basic_auth_config)
    
    @pytest.fixture
    def ralph_oidc_plugin(self, mock_oidc_config):
        """Create Ralph plugin instance with OIDC for testing."""
        return RalphPlugin(mock_oidc_config)
    
    def test_plugin_metadata(self):
        """Test plugin metadata is correct."""
        assert RalphPlugin.name == "ralph"
        assert "Ralph Learning Record Store" in RalphPlugin.description
        assert RalphPlugin.version == "1.0.0"
    
    def test_config_model(self):
        """Test plugin returns correct config model."""
        assert RalphPlugin.get_config_model() == RalphConfig
    
    def test_basic_auth_config_validation(self):
        """Test successful Basic Auth configuration validation."""
        config = {
            "endpoint": "https://ralph.example.com",
            "username": "test_user",
            "password": "test_password"
        }
        plugin = RalphPlugin(config)
        plugin.validate_config()  # Should not raise
    
    def test_oidc_config_validation(self):
        """Test successful OIDC configuration validation."""
        config = {
            "endpoint": "https://ralph.example.com",
            "oidc_token_url": "https://auth.example.com/oauth2/token",
            "oidc_client_id": "test_client",
            "oidc_client_secret": "test_secret"
        }
        plugin = RalphPlugin(config)
        plugin.validate_config()  # Should not raise
    
    def test_config_validation_missing_auth(self):
        """Test configuration validation fails with missing authentication."""
        config = {
            "endpoint": "https://ralph.example.com"
            # No auth credentials
        }
        # Ralph defaults to basic auth but requires username
        with pytest.raises(ValueError, match="Username required for basic authentication"):
            RalphPlugin(config)
    
    def test_config_validation_conflicting_auth(self):
        """Test configuration validation with mixed auth fields."""
        config = {
            "endpoint": "https://ralph.example.com",
            "username": "test_user",
            "password": "test_password",
            "oidc_token_url": "https://auth.example.com/oauth2/token",
            "oidc_client_id": "test_client",
            "oidc_client_secret": "test_secret"
        }
        # Ralph will auto-detect OIDC due to presence of oidc_token_url
        plugin = RalphPlugin(config)
        assert plugin.config.auth_method.value == "oidc"  # Should auto-detect OIDC
    
    def test_auth_method_detection_basic(self, ralph_basic_auth_plugin):
        """Test that Basic Auth is correctly detected."""
        assert ralph_basic_auth_plugin.config.auth_method.value == "basic"
        assert ralph_basic_auth_plugin.config.username == "test_user"
        assert ralph_basic_auth_plugin.config.password.get_secret_value() == "test_password"
    
    def test_auth_method_detection_oidc(self, ralph_oidc_plugin):
        """Test that OIDC is correctly detected."""
        assert ralph_oidc_plugin.config.auth_method.value == "oidc"
        assert ralph_oidc_plugin.config.oidc_token_url == "https://auth.example.com/oauth2/token"
        assert ralph_oidc_plugin.config.oidc_client_id == "test_client"
        assert ralph_oidc_plugin.config.oidc_client_secret.get_secret_value() == "test_secret"
    
    def test_basic_auth_headers(self, ralph_basic_auth_plugin):
        """Test that Basic Auth headers are correctly set."""
        headers = ralph_basic_auth_plugin.headers
        
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
        assert headers["X-Experience-API-Version"] == "1.0.3"
        assert headers["Content-Type"] == "application/json"
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_oidc_token_acquisition(self, ralph_oidc_plugin):
        """Test OIDC token acquisition and caching."""
        # Mock token endpoint
        respx.post("https://auth.example.com/oauth2/token").respond(
            200, json={
                "access_token": "test_access_token",
                "token_type": "Bearer",
                "expires_in": 3600
            }
        )
        
        token = await ralph_oidc_plugin._get_oidc_token()
        
        assert token == "test_access_token"
        assert ralph_oidc_plugin._oidc_token == "test_access_token"
        assert ralph_oidc_plugin._token_expires_at is not None
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_oidc_token_caching(self, ralph_oidc_plugin):
        """Test OIDC token caching behavior."""
        # Mock token endpoint
        respx.post("https://auth.example.com/oauth2/token").respond(
            200, json={
                "access_token": "test_access_token",
                "token_type": "Bearer",
                "expires_in": 3600
            }
        )
        
        # First call should fetch token
        token1 = await ralph_oidc_plugin._get_oidc_token()
        
        # Second call should use cached token
        token2 = await ralph_oidc_plugin._get_oidc_token()
        
        assert token1 == token2
        assert len(respx.calls) == 1  # Only one token request
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_oidc_token_refresh(self, ralph_oidc_plugin):
        """Test OIDC token refresh when expired."""
        # Set up expired token
        ralph_oidc_plugin._oidc_token = "expired_token"
        ralph_oidc_plugin._token_expires_at = datetime.now(timezone.utc)
        
        # Mock token endpoint
        respx.post("https://auth.example.com/oauth2/token").respond(
            200, json={
                "access_token": "new_access_token",
                "token_type": "Bearer",
                "expires_in": 3600
            }
        )
        
        token = await ralph_oidc_plugin._get_oidc_token()
        
        assert token == "new_access_token"
        assert ralph_oidc_plugin._oidc_token == "new_access_token"
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_oidc_headers_with_token(self, ralph_oidc_plugin):
        """Test that OIDC headers include Bearer token."""
        # Mock token endpoint
        respx.post("https://auth.example.com/oauth2/token").respond(
            200, json={
                "access_token": "test_access_token",
                "token_type": "Bearer",
                "expires_in": 3600
            }
        )
        
        headers = await ralph_oidc_plugin._get_headers()
        
        assert headers["Authorization"] == "Bearer test_access_token"
        assert headers["X-Experience-API-Version"] == "1.0.3"
        assert headers["Content-Type"] == "application/json"
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_post_statement_basic_auth_success(self, ralph_basic_auth_plugin):
        """Test successful statement posting with Basic Auth."""
        statement = {
            "actor": {"name": "test"},
            "verb": {"id": "http://example.com/verb"},
            "object": {"id": "http://example.com/object"}
        }
        
        respx.post("https://ralph-lrs.example.com/xapi/statements/").respond(
            200, json={"success": True}
        )
        
        result = await ralph_basic_auth_plugin.post_statement(statement)
        assert result["success"] == True
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_post_statement_oidc_success(self, ralph_oidc_plugin):
        """Test successful statement posting with OIDC."""
        statement = {
            "actor": {"name": "test"},
            "verb": {"id": "http://example.com/verb"},
            "object": {"id": "http://example.com/object"}
        }
        
        # Mock token endpoint
        respx.post("https://auth.example.com/oauth2/token").respond(
            200, json={
                "access_token": "test_access_token",
                "token_type": "Bearer",
                "expires_in": 3600
            }
        )
        
        # Mock statement posting
        respx.post("https://ralph-lrs.example.com/xapi/statements/").respond(
            200, json={"success": True}
        )
        
        result = await ralph_oidc_plugin.post_statement(statement)
        assert result["success"] == True
        
        # Verify Bearer token was used
        request = respx.calls[-1].request
        assert request.headers["Authorization"] == "Bearer test_access_token"
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_post_statement_retry_on_server_error(self, ralph_basic_auth_plugin):
        """Test retry logic on server errors."""
        statement = {
            "actor": {"name": "test"},
            "verb": {"id": "http://example.com/verb"},
            "object": {"id": "http://example.com/object"}
        }
        
        # First two requests fail with 500, third succeeds
        respx.post("https://ralph-lrs.example.com/xapi/statements/").mock(
            side_effect=[
                httpx.Response(500, json={"error": "server error"}),
                httpx.Response(500, json={"error": "server error"}),
                httpx.Response(200, json={"success": True})
            ]
        )
        
        result = await ralph_basic_auth_plugin.post_statement(statement)
        assert result["success"] == True
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_post_statement_max_retries_exceeded(self, ralph_basic_auth_plugin):
        """Test that max retries are respected."""
        statement = {
            "actor": {"name": "test"},
            "verb": {"id": "http://example.com/verb"},
            "object": {"id": "http://example.com/object"}
        }
        
        # All requests fail with 500
        respx.post("https://ralph-lrs.example.com/xapi/statements/").respond(500)
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await ralph_basic_auth_plugin.post_statement(statement)
        
        assert exc_info.value.status_code == 503
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_post_statement_no_retry_on_client_error(self, ralph_basic_auth_plugin):
        """Test that client errors (4xx) are not retried."""
        statement = {
            "actor": {"name": "test"},
            "verb": {"id": "http://example.com/verb"},
            "object": {"id": "http://example.com/object"}
        }
        
        respx.post("https://ralph-lrs.example.com/xapi/statements/").respond(
            400, json={"error": "bad request"}
        )
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await ralph_basic_auth_plugin.post_statement(statement)
        
        assert exc_info.value.status_code == 503
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_statements_success(self, ralph_basic_auth_plugin):
        """Test successful statements retrieval."""
        respx.get("https://ralph-lrs.example.com/xapi/statements/").respond(
            200, json={
                "statements": [
                    {"id": "stmt1", "actor": {"name": "test"}, "timestamp": "2023-01-02T00:00:00Z"},
                    {"id": "stmt2", "actor": {"name": "test"}, "timestamp": "2023-01-01T00:00:00Z"}
                ]
            }
        )
        
        result = await ralph_basic_auth_plugin.get_statements(actor_uuid="test-uuid")
        assert len(result) == 2
        # Should be sorted by timestamp descending
        assert result[0]["id"] == "stmt1"
        assert result[1]["id"] == "stmt2"
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_statements_with_filters(self, ralph_basic_auth_plugin):
        """Test statements retrieval with query filters."""
        respx.get("https://ralph-lrs.example.com/xapi/statements/").respond(
            200, json={"statements": []}
        )
        
        await ralph_basic_auth_plugin.get_statements(
            actor_uuid="test-uuid",
            verb="http://example.com/verb",
            object_id="http://example.com/activity",
            since=datetime.fromisoformat("2023-01-01T00:00:00+00:00"),
            until=datetime.fromisoformat("2023-12-31T23:59:59+00:00"),
            limit=10
        )
        
        # Verify request was made with correct query parameters
        request = respx.calls[0].request
        assert "agent=" in str(request.url)
        assert "verb=" in str(request.url)
        assert "activity=" in str(request.url)
        assert "since=" in str(request.url)
        assert "until=" in str(request.url)
        assert "limit=" in str(request.url)
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_statements_limit_enforcement(self, ralph_basic_auth_plugin):
        """Test that statement limit is enforced."""
        respx.get("https://ralph-lrs.example.com/xapi/statements/").respond(
            200, json={"statements": []}
        )
        
        await ralph_basic_auth_plugin.get_statements(
            actor_uuid="test-uuid",
            limit=100  # Should be capped at 50
        )
        
        # Verify limit was enforced
        request = respx.calls[0].request
        assert "limit=50" in str(request.url)
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_connection_timeout_retry(self, ralph_basic_auth_plugin):
        """Test retry on connection timeouts."""
        statement = {
            "actor": {"name": "test"},
            "verb": {"id": "http://example.com/verb"},
            "object": {"id": "http://example.com/object"}
        }
        
        # First request times out, second succeeds
        respx.post("https://ralph-lrs.example.com/xapi/statements/").mock(
            side_effect=[
                httpx.TimeoutException("Connection timeout"),
                httpx.Response(200, json={"success": True})
            ]
        )
        
        result = await ralph_basic_auth_plugin.post_statement(statement)
        assert result["success"] == True
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_oidc_token_error_handling(self, ralph_oidc_plugin):
        """Test OIDC token acquisition error handling."""
        # Mock token endpoint failure
        respx.post("https://auth.example.com/oauth2/token").respond(
            400, json={"error": "invalid_client"}
        )
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await ralph_oidc_plugin._get_oidc_token()
        
        assert exc_info.value.status_code == 503
    
    @pytest.mark.asyncio
    async def test_close_client(self, ralph_basic_auth_plugin):
        """Test closing HTTP client."""
        await ralph_basic_auth_plugin.close()
        # Should not raise any exceptions


class TestRalphConfig:
    """Test Ralph plugin configuration model."""
    
    def test_valid_basic_auth_config_creation(self):
        """Test valid Basic Auth configuration creation."""
        config = RalphConfig(
            endpoint="https://ralph.example.com",
            username="test_user",
            password="test_password",
            timeout=60,
            retry_attempts=5
        )
        
        assert config.endpoint == "https://ralph.example.com"
        assert config.username == "test_user"
        assert config.password.get_secret_value() == "test_password"
        assert config.timeout == 60
        assert config.retry_attempts == 5
    
    def test_valid_oidc_config_creation(self):
        """Test valid OIDC configuration creation."""
        config = RalphConfig(
            endpoint="https://ralph.example.com",
            oidc_token_url="https://auth.example.com/oauth2/token",
            oidc_client_id="test_client",
            oidc_client_secret="test_secret",
            timeout=60,
            retry_attempts=5
        )
        
        assert config.endpoint == "https://ralph.example.com"
        assert config.oidc_token_url == "https://auth.example.com/oauth2/token"
        assert config.oidc_client_id == "test_client"
        assert config.oidc_client_secret.get_secret_value() == "test_secret"
        assert config.timeout == 60
        assert config.retry_attempts == 5
    
    def test_config_env_prefix(self):
        """Test configuration environment prefix."""
        assert RalphConfig.Config.env_prefix == "RALPH_"
    
    def test_config_with_env_variables(self):
        """Test configuration with environment variables."""
        import os
        from learnmcp_xapi.plugins.ralph import RalphPlugin
        
        env_vars = {
            "RALPH_ENDPOINT": "https://env.example.com",
            "RALPH_USERNAME": "env_user",
            "RALPH_PASSWORD": "env_password"
        }
        
        with patch.dict(os.environ, env_vars):
            config_dict = RalphPlugin.load_config_from_env("ralph")
            
            assert config_dict["endpoint"] == "https://env.example.com"
            assert config_dict["username"] == "env_user"
            assert config_dict["password"] == "env_password"
    
    def test_config_endpoint_validation(self):
        """Test endpoint validation."""
        # Valid HTTPS endpoint
        config = RalphConfig(
            endpoint="https://example.com",
            username="user",
            password="password"
        )
        assert config.endpoint == "https://example.com"
        
        # Valid HTTP endpoint
        config = RalphConfig(
            endpoint="http://localhost:8080",
            username="user",
            password="password"
        )
        assert config.endpoint == "http://localhost:8080"
        
        # Invalid endpoint
        with pytest.raises(ValueError, match="must start with http"):
            RalphConfig(
                endpoint="invalid-url",
                username="user",
                password="password"
            )
    
    def test_config_endpoint_trailing_slash_removal(self):
        """Test that trailing slash is removed from endpoint."""
        config = RalphConfig(
            endpoint="https://example.com/",
            username="user",
            password="password"
        )
        assert config.endpoint == "https://example.com"
    
    def test_config_auth_validation(self):
        """Test authentication validation logic."""
        # Valid Basic Auth
        config = RalphConfig(
            endpoint="https://example.com",
            username="user",
            password="password"
        )
        # Should not raise
        
        # Valid OIDC
        config = RalphConfig(
            endpoint="https://example.com",
            oidc_token_url="https://auth.example.com/oauth2/token",
            oidc_client_id="client",
            oidc_client_secret="secret"
        )
        # Should not raise
        
        # Missing auth (Ralph defaults to basic but requires username)
        with pytest.raises(ValueError, match="Username required for basic authentication"):
            RalphConfig(endpoint="https://example.com")
        
        # Mixed auth fields (Ralph will auto-detect OIDC)
        config = RalphConfig(
            endpoint="https://example.com",
            username="user",
            password="password",
            oidc_token_url="https://auth.example.com/oauth2/token",
            oidc_client_id="client",
            oidc_client_secret="secret"
        )
        # Should auto-detect OIDC
        assert config.auth_method.value == "oidc"


class TestRalphPluginIntegration:
    """Test Ralph plugin integration with the plugin system."""
    
    def test_plugin_implements_interface(self):
        """Test that plugin properly implements the base interface."""
        from learnmcp_xapi.plugins.base import LRSPlugin
        
        assert issubclass(RalphPlugin, LRSPlugin)
        
        # Test required class attributes
        assert hasattr(RalphPlugin, 'name')
        assert hasattr(RalphPlugin, 'description')
        assert hasattr(RalphPlugin, 'version')
        
        # Test required methods
        assert hasattr(RalphPlugin, 'get_config_model')
        assert hasattr(RalphPlugin, 'validate_config')
        assert hasattr(RalphPlugin, 'post_statement')
        assert hasattr(RalphPlugin, 'get_statements')
        assert hasattr(RalphPlugin, 'close')
    
    def test_plugin_registration(self):
        """Test that plugin can be registered in the registry."""
        from learnmcp_xapi.plugins.registry import PluginRegistry
        
        registry = PluginRegistry()
        registry.register(RalphPlugin)
        
        assert 'ralph' in registry
        assert registry.get('ralph') == RalphPlugin
    
    def test_plugin_factory_creation_basic_auth(self):
        """Test that plugin can be created via factory with Basic Auth."""
        from learnmcp_xapi.plugins.factory import PluginFactory
        from learnmcp_xapi.plugins.registry import PluginRegistry
        
        # Setup registry
        registry = PluginRegistry()
        registry.register(RalphPlugin)
        
        config = {
            "endpoint": "https://test.com",
            "username": "test_user",
            "password": "test_password"
        }
        
        with patch('learnmcp_xapi.plugins.factory.plugin_registry', registry):
            plugin = PluginFactory.create_plugin('ralph', additional_config=config)
            assert isinstance(plugin, RalphPlugin)
            assert plugin.config.endpoint == "https://test.com"
            assert plugin.config.auth_method.value == "basic"
    
    def test_plugin_factory_creation_oidc(self):
        """Test that plugin can be created via factory with OIDC."""
        from learnmcp_xapi.plugins.factory import PluginFactory
        from learnmcp_xapi.plugins.registry import PluginRegistry
        
        # Setup registry
        registry = PluginRegistry()
        registry.register(RalphPlugin)
        
        config = {
            "endpoint": "https://test.com",
            "oidc_token_url": "https://auth.example.com/oauth2/token",
            "oidc_client_id": "test_client",
            "oidc_client_secret": "test_secret"
        }
        
        with patch('learnmcp_xapi.plugins.factory.plugin_registry', registry):
            plugin = PluginFactory.create_plugin('ralph', additional_config=config)
            assert isinstance(plugin, RalphPlugin)
            assert plugin.config.endpoint == "https://test.com"
            assert plugin.config.auth_method.value == "oidc"