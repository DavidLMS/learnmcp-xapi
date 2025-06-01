"""Integration tests for the plugin system."""

import pytest
import respx
import httpx
from unittest.mock import patch, MagicMock
import tempfile
import os
import json

from learnmcp_xapi.plugins.registry import PluginRegistry
from learnmcp_xapi.plugins.factory import PluginFactory
from learnmcp_xapi.plugins.lrsql import LRSSQLPlugin
from learnmcp_xapi.plugins.ralph import RalphPlugin
from learnmcp_xapi.plugins.veracity import VeracityPlugin


class TestPluginSystemIntegration:
    """Test the complete plugin system integration."""
    
    @pytest.fixture
    def plugin_registry(self):
        """Create a plugin registry with all plugins registered."""
        registry = PluginRegistry()
        registry.register(LRSSQLPlugin)
        registry.register(RalphPlugin)
        registry.register(VeracityPlugin)
        return registry
    
    def test_plugin_registration_and_discovery(self, plugin_registry):
        """Test that all plugins can be registered and discovered."""
        assert 'lrsql' in plugin_registry
        assert 'ralph' in plugin_registry
        assert 'veracity' in plugin_registry
        
        assert plugin_registry.get('lrsql') == LRSSQLPlugin
        assert plugin_registry.get('ralph') == RalphPlugin
        assert plugin_registry.get('veracity') == VeracityPlugin
        
        assert plugin_registry.list_plugins() == ['lrsql', 'ralph', 'veracity']
    
    def test_plugin_factory_creation_lrsql(self, plugin_registry):
        """Test creating LRS SQL plugin via factory."""
        config = {
            "endpoint": "https://lrsql.example.com",
            "key": "test_key",
            "secret": "test_secret"
        }
        
        with patch('learnmcp_xapi.plugins.factory.plugin_registry', plugin_registry):
            plugin = PluginFactory.create_plugin('lrsql', additional_config=config)
            
            assert isinstance(plugin, LRSSQLPlugin)
            assert plugin.config.endpoint == "https://lrsql.example.com"
            assert plugin.config.key == "test_key"
    
    def test_plugin_factory_creation_ralph_basic_auth(self, plugin_registry):
        """Test creating Ralph plugin with Basic Auth via factory."""
        config = {
            "endpoint": "https://ralph.example.com",
            "username": "test_user",
            "password": "test_password"
        }
        
        with patch('learnmcp_xapi.plugins.factory.plugin_registry', plugin_registry):
            plugin = PluginFactory.create_plugin('ralph', additional_config=config)
            
            assert isinstance(plugin, RalphPlugin)
            assert plugin.config.endpoint == "https://ralph.example.com"
            assert plugin.auth_method == "basic"
    
    def test_plugin_factory_creation_ralph_oidc(self, plugin_registry):
        """Test creating Ralph plugin with OIDC via factory."""
        config = {
            "endpoint": "https://ralph.example.com",
            "oidc_issuer": "https://auth.example.com",
            "oidc_client_id": "test_client",
            "oidc_client_secret": "test_secret"
        }
        
        with patch('learnmcp_xapi.plugins.factory.plugin_registry', plugin_registry):
            plugin = PluginFactory.create_plugin('ralph', additional_config=config)
            
            assert isinstance(plugin, RalphPlugin)
            assert plugin.config.endpoint == "https://ralph.example.com"
            assert plugin.auth_method == "oidc"
    
    def test_plugin_factory_creation_veracity(self, plugin_registry):
        """Test creating Veracity plugin via factory."""
        config = {
            "endpoint": "https://test.lrs.io/xapi",
            "username": "access_key",
            "password": "access_secret"
        }
        
        with patch('learnmcp_xapi.plugins.factory.plugin_registry', plugin_registry):
            plugin = PluginFactory.create_plugin('veracity', additional_config=config)
            
            assert isinstance(plugin, VeracityPlugin)
            # Should clean the endpoint
            assert plugin.config.endpoint == "https://test.lrs.io"
    
    def test_plugin_factory_with_env_config(self, plugin_registry):
        """Test plugin factory with environment variable configuration."""
        env_vars = {
            "LRSQL_ENDPOINT": "https://env-lrsql.example.com",
            "LRSQL_KEY": "env_key",
            "LRSQL_SECRET": "env_secret",
            "LRSQL_TIMEOUT": "60"
        }
        
        with patch.dict(os.environ, env_vars):
            with patch('learnmcp_xapi.plugins.factory.plugin_registry', plugin_registry):
                plugin = PluginFactory.create_plugin('lrsql')
                
                assert isinstance(plugin, LRSSQLPlugin)
                assert plugin.config.endpoint == "https://env-lrsql.example.com"
                assert plugin.config.key == "env_key"
                assert plugin.config.timeout == 60
    
    def test_plugin_factory_with_file_config(self, plugin_registry):
        """Test plugin factory with file-based configuration."""
        config_data = {
            "lrsql": {
                "endpoint": "https://file-lrsql.example.com",
                "key": "file_key",
                "secret": "file_secret",
                "timeout": 45
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name
        
        try:
            with patch('learnmcp_xapi.plugins.factory.plugin_registry', plugin_registry):
                plugin = PluginFactory.create_plugin('lrsql', config_file=config_file)
                
                assert isinstance(plugin, LRSSQLPlugin)
                assert plugin.config.endpoint == "https://file-lrsql.example.com"
                assert plugin.config.key == "file_key"
                assert plugin.config.timeout == 45
        finally:
            os.unlink(config_file)
    
    def test_plugin_factory_config_precedence(self, plugin_registry):
        """Test configuration precedence: file < env < additional_config."""
        config_data = {
            "lrsql": {
                "endpoint": "https://file-lrsql.example.com",
                "key": "file_key",
                "secret": "file_secret",
                "timeout": 30
            }
        }
        
        env_vars = {
            "LRSQL_ENDPOINT": "https://env-lrsql.example.com",
            "LRSQL_KEY": "env_key"
            # Note: secret and timeout from file should be used
        }
        
        additional_config = {
            "endpoint": "https://override-lrsql.example.com"
            # Note: key from env and secret/timeout from file should be used
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name
        
        try:
            with patch.dict(os.environ, env_vars):
                with patch('learnmcp_xapi.plugins.factory.plugin_registry', plugin_registry):
                    plugin = PluginFactory.create_plugin(
                        'lrsql', 
                        config_file=config_file,
                        additional_config=additional_config
                    )
                    
                    # Highest precedence: additional_config
                    assert plugin.config.endpoint == "https://override-lrsql.example.com"
                    # Medium precedence: env vars
                    assert plugin.config.key == "env_key"
                    # Lowest precedence: file config (used when not overridden)
                    assert plugin.config.secret.get_secret_value() == "file_secret"
                    assert plugin.config.timeout == 30
        finally:
            os.unlink(config_file)
    
    def test_plugin_factory_invalid_plugin(self, plugin_registry):
        """Test factory behavior with invalid plugin name."""
        with patch('learnmcp_xapi.plugins.factory.plugin_registry', plugin_registry):
            with pytest.raises(ValueError, match="Unknown plugin: nonexistent"):
                PluginFactory.create_plugin('nonexistent')
    
    def test_plugin_factory_invalid_config(self, plugin_registry):
        """Test factory behavior with invalid configuration."""
        config = {
            "endpoint": "invalid-endpoint",  # Missing protocol
            "key": "test_key",
            "secret": "test_secret"
        }
        
        with patch('learnmcp_xapi.plugins.factory.plugin_registry', plugin_registry):
            with pytest.raises(ValueError):
                PluginFactory.create_plugin('lrsql', additional_config=config)
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_end_to_end_lrsql_plugin_flow(self, plugin_registry):
        """Test complete end-to-end flow with LRS SQL plugin."""
        config = {
            "endpoint": "https://lrsql.example.com",
            "key": "test_key",
            "secret": "test_secret"
        }
        
        # Mock LRS responses
        respx.post("https://lrsql.example.com/xapi/statements").respond(
            201, json={"id": "test-statement-id"}
        )
        
        respx.get("https://lrsql.example.com/xapi/statements").respond(
            200, json={
                "statements": [
                    {"id": "stmt1", "timestamp": "2023-01-01T00:00:00Z"}
                ]
            }
        )
        
        with patch('learnmcp_xapi.plugins.factory.plugin_registry', plugin_registry):
            # Create plugin via factory
            plugin = PluginFactory.create_plugin('lrsql', additional_config=config)
            
            # Test statement posting
            statement = {
                "actor": {"name": "test"},
                "verb": {"id": "http://example.com/verb"},
                "object": {"id": "http://example.com/object"}
            }
            
            result = await plugin.post_statement(statement)
            assert result["id"] == "test-statement-id"
            
            # Test statement retrieval
            statements = await plugin.get_statements(actor_uuid="test-uuid")
            assert len(statements) == 1
            assert statements[0]["id"] == "stmt1"
            
            # Test cleanup
            await plugin.close()
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_end_to_end_ralph_basic_auth_flow(self, plugin_registry):
        """Test complete end-to-end flow with Ralph plugin using Basic Auth."""
        config = {
            "endpoint": "https://ralph.example.com",
            "username": "test_user",
            "password": "test_password"
        }
        
        # Mock Ralph responses
        respx.post("https://ralph.example.com/xapi/statements/").respond(
            200, json={"success": True}
        )
        
        respx.get("https://ralph.example.com/xapi/statements/").respond(
            200, json={
                "statements": [
                    {"id": "stmt1", "timestamp": "2023-01-01T00:00:00Z"}
                ]
            }
        )
        
        with patch('learnmcp_xapi.plugins.factory.plugin_registry', plugin_registry):
            # Create plugin via factory
            plugin = PluginFactory.create_plugin('ralph', additional_config=config)
            
            # Verify auth method detection
            assert plugin.auth_method == "basic"
            
            # Test statement posting
            statement = {
                "actor": {"name": "test"},
                "verb": {"id": "http://example.com/verb"},
                "object": {"id": "http://example.com/object"}
            }
            
            result = await plugin.post_statement(statement)
            assert result["success"] == True
            
            # Test statement retrieval
            statements = await plugin.get_statements(actor_uuid="test-uuid")
            assert len(statements) == 1
            assert statements[0]["id"] == "stmt1"
            
            # Test cleanup
            await plugin.close()
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_end_to_end_ralph_oidc_flow(self, plugin_registry):
        """Test complete end-to-end flow with Ralph plugin using OIDC."""
        config = {
            "endpoint": "https://ralph.example.com",
            "oidc_issuer": "https://auth.example.com",
            "oidc_client_id": "test_client",
            "oidc_client_secret": "test_secret"
        }
        
        # Mock OIDC token endpoint
        respx.post("https://auth.example.com/oauth2/token").respond(
            200, json={
                "access_token": "test_access_token",
                "token_type": "Bearer",
                "expires_in": 3600
            }
        )
        
        # Mock Ralph responses
        respx.post("https://ralph.example.com/xapi/statements/").respond(
            200, json={"success": True}
        )
        
        with patch('learnmcp_xapi.plugins.factory.plugin_registry', plugin_registry):
            # Create plugin via factory
            plugin = PluginFactory.create_plugin('ralph', additional_config=config)
            
            # Verify auth method detection
            assert plugin.auth_method == "oidc"
            
            # Test statement posting (will trigger token acquisition)
            statement = {
                "actor": {"name": "test"},
                "verb": {"id": "http://example.com/verb"},
                "object": {"id": "http://example.com/object"}
            }
            
            result = await plugin.post_statement(statement)
            assert result["success"] == True
            
            # Verify OIDC token was acquired and used
            assert len(respx.calls) == 2  # Token request + statement post
            token_request = respx.calls[0].request
            statement_request = respx.calls[1].request
            
            assert "oauth2/token" in str(token_request.url)
            assert statement_request.headers["Authorization"] == "Bearer test_access_token"
            
            # Test cleanup
            await plugin.close()
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_end_to_end_veracity_flow(self, plugin_registry):
        """Test complete end-to-end flow with Veracity plugin."""
        config = {
            "endpoint": "https://test.lrs.io/xapi",  # Will be cleaned
            "username": "access_key",
            "password": "access_secret"
        }
        
        # Mock Veracity responses
        respx.post("https://test.lrs.io/xapi/statements").respond(
            201, json=["test-statement-id"]
        )
        
        respx.get("https://test.lrs.io/xapi/statements").respond(
            200, json={
                "statements": [
                    {"id": "stmt1", "timestamp": "2023-01-01T00:00:00Z"}
                ]
            }
        )
        
        with patch('learnmcp_xapi.plugins.factory.plugin_registry', plugin_registry):
            # Create plugin via factory
            plugin = PluginFactory.create_plugin('veracity', additional_config=config)
            
            # Verify endpoint was cleaned
            assert plugin.config.endpoint == "https://test.lrs.io"
            
            # Test statement posting
            statement = {
                "actor": {"name": "test"},
                "verb": {"id": "http://example.com/verb"},
                "object": {"id": "http://example.com/object"}
            }
            
            result = await plugin.post_statement(statement)
            assert result["id"] == "test-statement-id"
            assert result["stored"] == True
            
            # Test statement retrieval
            statements = await plugin.get_statements(actor_uuid="test-uuid")
            assert len(statements) == 1
            assert statements[0]["id"] == "stmt1"
            
            # Test cleanup
            await plugin.close()
    
    def test_plugin_metadata_consistency(self, plugin_registry):
        """Test that all plugins have consistent metadata."""
        for plugin_name in plugin_registry.list_plugins():
            plugin_class = plugin_registry.get(plugin_name)
            
            # All plugins should have required metadata
            assert hasattr(plugin_class, 'name')
            assert hasattr(plugin_class, 'description')
            assert hasattr(plugin_class, 'version')
            
            # Metadata should be strings
            assert isinstance(plugin_class.name, str)
            assert isinstance(plugin_class.description, str)
            assert isinstance(plugin_class.version, str)
            
            # Name should match registry key
            assert plugin_class.name == plugin_name
    
    def test_plugin_interface_consistency(self, plugin_registry):
        """Test that all plugins implement the required interface consistently."""
        from learnmcp_xapi.plugins.base import LRSPlugin
        
        for plugin_name in plugin_registry.list_plugins():
            plugin_class = plugin_registry.get(plugin_name)
            
            # All plugins should inherit from LRSPlugin
            assert issubclass(plugin_class, LRSPlugin)
            
            # All plugins should implement required methods
            required_methods = [
                'get_config_model',
                'validate_config', 
                'post_statement',
                'get_statements',
                'close'
            ]
            
            for method_name in required_methods:
                assert hasattr(plugin_class, method_name)
                assert callable(getattr(plugin_class, method_name))
    
    @pytest.mark.asyncio
    async def test_plugin_resource_cleanup(self, plugin_registry):
        """Test that all plugins properly clean up resources."""
        configs = {
            'lrsql': {
                "endpoint": "https://lrsql.example.com",
                "key": "test_key",
                "secret": "test_secret"
            },
            'ralph': {
                "endpoint": "https://ralph.example.com",
                "username": "test_user",
                "password": "test_password"
            },
            'veracity': {
                "endpoint": "https://test.lrs.io",
                "username": "access_key",
                "password": "access_secret"
            }
        }
        
        with patch('learnmcp_xapi.plugins.factory.plugin_registry', plugin_registry):
            plugins = []
            
            # Create all plugins
            for plugin_name, config in configs.items():
                plugin = PluginFactory.create_plugin(plugin_name, additional_config=config)
                plugins.append(plugin)
            
            # Close all plugins (should not raise exceptions)
            for plugin in plugins:
                await plugin.close()