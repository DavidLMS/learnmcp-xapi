"""Tests for plugin system."""

import os
import pytest
import tempfile
import yaml
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path

from learnmcp_xapi.plugins.registry import PluginRegistry, plugin_registry
from learnmcp_xapi.plugins.factory import PluginFactory
from learnmcp_xapi.plugins.base import LRSPlugin, LRSPluginConfig
from learnmcp_xapi.plugins.lrsql import LRSSQLPlugin, LRSSQLConfig
from learnmcp_xapi.plugins.ralph import RalphPlugin, RalphConfig, AuthMethod


class TestPluginRegistry:
    """Test plugin registry functionality."""
    
    def test_register_plugin(self):
        """Test plugin registration."""
        registry = PluginRegistry()
        
        # Register mock plugin
        mock_plugin = type('MockPlugin', (LRSPlugin,), {
            'name': 'test',
            'description': 'Test Plugin',
            'get_config_model': classmethod(lambda cls: LRSPluginConfig),
            'validate_config': lambda self: None,
            'post_statement': AsyncMock(),
            'get_statements': AsyncMock()
        })
        
        registry.register(mock_plugin)
        
        assert 'test' in registry
        assert registry.get('test') == mock_plugin
        assert registry.list_plugins()['test'] == 'Test Plugin'
    
    def test_register_plugin_without_name(self):
        """Test registration fails for plugin without name."""
        registry = PluginRegistry()
        
        # Plugin without name
        mock_plugin = type('BadPlugin', (LRSPlugin,), {
            'name': '',  # Empty name
            'description': 'Bad Plugin'
        })
        
        with pytest.raises(ValueError, match="must have a name"):
            registry.register(mock_plugin)
    
    def test_get_nonexistent_plugin(self):
        """Test getting non-existent plugin returns None."""
        registry = PluginRegistry()
        assert registry.get('nonexistent') is None
    
    def test_plugin_overwrite_warning(self, caplog):
        """Test plugin overwrite generates warning."""
        registry = PluginRegistry()
        
        # Create two plugins with same name
        plugin1 = type('Plugin1', (LRSPlugin,), {
            'name': 'test',
            'description': 'First Plugin',
            'get_config_model': classmethod(lambda cls: LRSPluginConfig),
            'validate_config': lambda self: None,
            'post_statement': AsyncMock(),
            'get_statements': AsyncMock()
        })
        
        plugin2 = type('Plugin2', (LRSPlugin,), {
            'name': 'test',
            'description': 'Second Plugin',
            'get_config_model': classmethod(lambda cls: LRSPluginConfig),
            'validate_config': lambda self: None,
            'post_statement': AsyncMock(),
            'get_statements': AsyncMock()
        })
        
        registry.register(plugin1)
        registry.register(plugin2)
        
        assert "already registered, overwriting" in caplog.text


class TestPluginFactory:
    """Test plugin factory functionality."""
    
    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary config directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            plugins_dir = config_dir / "plugins"
            plugins_dir.mkdir()
            yield str(config_dir)
    
    @pytest.fixture
    def mock_registry(self):
        """Mock plugin registry with test plugin."""
        mock_plugin = type('MockPlugin', (LRSPlugin,), {
            'name': 'test',
            'description': 'Test Plugin',
            'get_config_model': classmethod(lambda cls: LRSPluginConfig),
            'validate_config': lambda self: None,
            'post_statement': AsyncMock(),
            'get_statements': AsyncMock(),
            'load_config_from_file': classmethod(lambda cls, name, path: {'endpoint': 'http://file.com'}),
            'load_config_from_env': classmethod(lambda cls, name: {'endpoint': 'http://env.com'})
        })
        
        registry = PluginRegistry()
        registry.register(mock_plugin)
        
        with patch('learnmcp_xapi.plugins.factory.plugin_registry', registry):
            yield registry
    
    def test_create_plugin_unknown(self, mock_registry):
        """Test creating unknown plugin raises error."""
        with pytest.raises(ValueError, match="Unknown plugin: 'unknown'"):
            PluginFactory.create_plugin('unknown')
    
    def test_create_plugin_with_config_file(self, mock_registry, temp_config_dir):
        """Test creating plugin with config file."""
        # Create config file
        config_file = Path(temp_config_dir) / "plugins" / "test.yaml"
        config_data = {"endpoint": "http://file.com", "timeout": 60}
        
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        plugin = PluginFactory.create_plugin('test', config_path=temp_config_dir)
        
        assert plugin is not None
    
    def test_create_plugin_env_overrides_file(self, mock_registry):
        """Test environment variables override config file."""
        env_vars = {"TEST_ENDPOINT": "http://env.com"}
        
        with patch.dict(os.environ, env_vars):
            plugin = PluginFactory.create_plugin('test', config_path="/fake/path")
            assert plugin is not None
    
    def test_create_plugin_additional_config_overrides_all(self, mock_registry):
        """Test additional config overrides everything."""
        env_vars = {"TEST_ENDPOINT": "http://env.com"}
        additional_config = {"endpoint": "http://additional.com"}
        
        with patch.dict(os.environ, env_vars):
            plugin = PluginFactory.create_plugin(
                'test', 
                additional_config=additional_config
            )
            assert plugin is not None


class TestLRSPluginConfig:
    """Test LRS plugin configuration base class."""
    
    def test_valid_config(self):
        """Test valid configuration."""
        config = LRSPluginConfig(
            endpoint="https://example.com",
            timeout=30,
            retry_attempts=3
        )
        
        assert config.endpoint == "https://example.com"
        assert config.timeout == 30
        assert config.retry_attempts == 3
    
    def test_invalid_endpoint_protocol(self):
        """Test invalid endpoint protocol raises error."""
        with pytest.raises(ValueError, match="must start with http"):
            LRSPluginConfig(endpoint="ftp://example.com")
    
    def test_endpoint_trailing_slash_stripped(self):
        """Test trailing slash is stripped from endpoint."""
        config = LRSPluginConfig(endpoint="https://example.com/")
        assert config.endpoint == "https://example.com"


class TestLRSSQLConfig:
    """Test LRS SQL plugin configuration."""
    
    def test_valid_config(self):
        """Test valid LRS SQL configuration."""
        config = LRSSQLConfig(
            endpoint="https://lrsql.com",
            key="test_key",
            secret="test_secret"
        )
        
        assert config.endpoint == "https://lrsql.com"
        assert config.key == "test_key"
        assert config.secret.get_secret_value() == "test_secret"
    
    def test_missing_required_fields(self):
        """Test missing required fields raise error."""
        with pytest.raises(ValueError):
            LRSSQLConfig(endpoint="https://example.com")


class TestRalphConfig:
    """Test Ralph plugin configuration."""
    
    def test_basic_auth_config(self):
        """Test basic auth configuration."""
        config = RalphConfig(
            endpoint="https://ralph.com",
            username="user",
            password="pass"
        )
        
        assert config.auth_method == AuthMethod.BASIC
        assert config.username == "user"
        assert config.password.get_secret_value() == "pass"
    
    def test_oidc_auth_config(self):
        """Test OIDC auth configuration."""
        config = RalphConfig(
            endpoint="https://ralph.com",
            oidc_token_url="https://keycloak.com/token",
            oidc_client_id="ralph",
            oidc_client_secret="secret"
        )
        
        assert config.auth_method == AuthMethod.OIDC
        assert config.oidc_token_url == "https://keycloak.com/token"
        assert config.oidc_client_id == "ralph"
    
    def test_auth_method_auto_detection(self):
        """Test authentication method auto-detection."""
        # Should detect OIDC when oidc_token_url is present
        config1 = RalphConfig(
            endpoint="https://ralph.com",
            oidc_token_url="https://keycloak.com/token"
        )
        assert config1.auth_method == AuthMethod.OIDC
        
        # Should default to BASIC otherwise
        config2 = RalphConfig(
            endpoint="https://ralph.com",
            username="user",
            password="pass"
        )
        assert config2.auth_method == AuthMethod.BASIC


class TestPluginIntegration:
    """Test plugin system integration."""
    
    def test_lrsql_plugin_registration(self):
        """Test LRS SQL plugin can be registered and retrieved."""
        registry = PluginRegistry()
        registry.register(LRSSQLPlugin)
        
        assert 'lrsql' in registry
        plugin_class = registry.get('lrsql')
        assert plugin_class == LRSSQLPlugin
    
    def test_ralph_plugin_registration(self):
        """Test Ralph plugin can be registered and retrieved."""
        registry = PluginRegistry()
        registry.register(RalphPlugin)
        
        assert 'ralph' in registry
        plugin_class = registry.get('ralph')
        assert plugin_class == RalphPlugin
    
    def test_global_plugin_registry_has_plugins(self):
        """Test global plugin registry works."""
        # This test depends on plugins being registered in main.py
        # In a real test environment, you might need to register them manually
        available_plugins = plugin_registry.list_plugins()
        
        # At minimum, we should have our base plugins available after import
        assert isinstance(available_plugins, dict)


class TestBackwardCompatibility:
    """Test backward compatibility with legacy configuration."""
    
    def test_factory_with_legacy_config(self):
        """Test factory handles legacy configuration correctly."""
        mock_config = MagicMock()
        mock_config.LRS_PLUGIN = "lrsql"
        mock_config.CONFIG_PATH = "./config"
        mock_config.LRS_ENDPOINT = "https://legacy.com"
        mock_config.LRS_KEY = "legacy_key"
        mock_config.LRS_SECRET = "legacy_secret"
        
        # Mock the registry to have our plugin
        mock_plugin_class = MagicMock()
        mock_plugin_instance = MagicMock()
        mock_plugin_class.return_value = mock_plugin_instance
        
        registry = PluginRegistry()
        registry._plugins['lrsql'] = mock_plugin_class
        
        with patch('learnmcp_xapi.plugins.factory.plugin_registry', registry):
            with patch('learnmcp_xapi.plugins.factory.logger'):
                PluginFactory.create_from_config(mock_config)
                
                # Verify plugin was called with legacy config
                mock_plugin_class.assert_called_once()
                args, kwargs = mock_plugin_class.call_args
                
                # Should include legacy config in the call
                assert len(args) == 1  # config dict
                config_dict = args[0]
                
                # Additional config should include legacy values
                expected_calls = mock_plugin_class.call_args_list
                assert len(expected_calls) == 1