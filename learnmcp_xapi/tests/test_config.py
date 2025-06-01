"""Tests for configuration module with plugin system."""

import os
import pytest
from unittest.mock import patch
from pathlib import Path

from learnmcp_xapi.config import Config


class TestConfig:
    """Test configuration validation and defaults."""
    
    def test_config_with_all_required_env_vars(self):
        """Test config initialization with required environment variables."""
        env_vars = {
            "ACTOR_UUID": "123e4567-e89b-12d3-a456-426614174000",
            "LRS_PLUGIN": "lrsql"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = Config()
            config.validate()  # Should not raise
            
            assert config.LRS_PLUGIN == "lrsql"
            assert config.ACTOR_UUID == "123e4567-e89b-12d3-a456-426614174000"
            assert config.CONFIG_PATH == "./config"
    
    def test_config_with_legacy_lrs_vars(self):
        """Test config with legacy LRS variables (backward compatibility)."""
        env_vars = {
            "LRS_ENDPOINT": "https://example.com/xapi",
            "LRS_KEY": "test_key",
            "LRS_SECRET": "test_secret", 
            "ACTOR_UUID": "123e4567-e89b-12d3-a456-426614174000",
            "LRS_PLUGIN": "lrsql"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = Config()
            config.validate()  # Should not raise
            
            assert config.LRS_ENDPOINT == "https://example.com/xapi"
            assert config.LRS_KEY == "test_key"
            assert config.LRS_SECRET == "test_secret"
    
    def test_config_missing_actor_uuid(self):
        """Test config validation fails when ACTOR_UUID is missing."""
        env_vars = {
            "LRS_PLUGIN": "lrsql"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = Config()
            with pytest.raises(ValueError, match="ACTOR_UUID is required"):
                config.validate()
    
    def test_config_missing_lrs_plugin(self):
        """Test config validation with missing LRS_PLUGIN (uses default)."""
        env_vars = {
            "ACTOR_UUID": "123e4567-e89b-12d3-a456-426614174000"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = Config()
            config.validate()  # Should not raise
            assert config.LRS_PLUGIN == "lrsql"  # Default
    
    def test_config_legacy_validation_missing_key(self):
        """Test legacy validation fails when LRS_KEY is missing but LRS_ENDPOINT is set."""
        env_vars = {
            "LRS_ENDPOINT": "https://example.com/xapi",
            "LRS_SECRET": "test_secret",
            "ACTOR_UUID": "123e4567-e89b-12d3-a456-426614174000",
            "CONFIG_PATH": "/nonexistent/path"  # Force legacy mode
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with patch('pathlib.Path.exists', return_value=False):
                config = Config()
                with pytest.raises(ValueError, match="LRS_KEY and LRS_SECRET are required"):
                    config.validate()
    
    def test_config_legacy_validation_missing_secret(self):
        """Test legacy validation fails when LRS_SECRET is missing but LRS_ENDPOINT is set."""
        env_vars = {
            "LRS_ENDPOINT": "https://example.com/xapi",
            "LRS_KEY": "test_key",
            "ACTOR_UUID": "123e4567-e89b-12d3-a456-426614174000",
            "CONFIG_PATH": "/nonexistent/path"  # Force legacy mode
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with patch('pathlib.Path.exists', return_value=False):
                config = Config()
                with pytest.raises(ValueError, match="LRS_KEY and LRS_SECRET are required"):
                    config.validate()
    
    def test_config_development_allows_http(self):
        """Test that HTTP is allowed in development mode (legacy config)."""
        env_vars = {
            "LRS_ENDPOINT": "http://localhost:8080/xapi",
            "LRS_KEY": "test_key",
            "LRS_SECRET": "test_secret",
            "ACTOR_UUID": "123e4567-e89b-12d3-a456-426614174000",
            "ENV": "development",
            "CONFIG_PATH": "/nonexistent/path"  # Force legacy mode
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with patch('pathlib.Path.exists', return_value=False):
                config = Config()
                config.validate()  # Should not raise
                assert config.LRS_ENDPOINT == "http://localhost:8080/xapi"
    
    def test_config_production_requires_https(self):
        """Test that HTTPS is required in production mode (legacy config)."""
        env_vars = {
            "LRS_ENDPOINT": "http://example.com/xapi",
            "LRS_KEY": "test_key",
            "LRS_SECRET": "test_secret", 
            "ACTOR_UUID": "123e4567-e89b-12d3-a456-426614174000",
            "ENV": "production",
            "CONFIG_PATH": "/nonexistent/path"  # Force legacy mode
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with patch('pathlib.Path.exists', return_value=False):
                config = Config()
                with pytest.raises(ValueError, match="LRS_ENDPOINT must use HTTPS in production"):
                    config.validate()
    
    def test_config_plugin_defaults(self):
        """Test plugin configuration defaults."""
        env_vars = {
            "ACTOR_UUID": "123e4567-e89b-12d3-a456-426614174000"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = Config()
            assert config.LRS_PLUGIN == "lrsql"
            assert config.CONFIG_PATH == "./config"
    
    def test_config_custom_plugin_and_path(self):
        """Test custom plugin and config path."""
        env_vars = {
            "ACTOR_UUID": "123e4567-e89b-12d3-a456-426614174000",
            "LRS_PLUGIN": "ralph",
            "CONFIG_PATH": "/custom/config/path"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = Config()
            assert config.LRS_PLUGIN == "ralph"
            assert config.CONFIG_PATH == "/custom/config/path"
    
    def test_config_accepts_any_actor_uuid_format(self):
        """Test config accepts any non-empty actor UUID format."""
        env_vars = {
            "ACTOR_UUID": "student-12345",  # Any format is fine
            "LRS_PLUGIN": "lrsql"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = Config()
            config.validate()  # Should not raise
            assert config.ACTOR_UUID == "student-12345"
    
    def test_config_default_environment(self):
        """Test default environment is 'development'."""
        env_vars = {
            "ACTOR_UUID": "123e4567-e89b-12d3-a456-426614174000"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = Config()
            assert config.ENV == "development"
    
    def test_config_optional_settings(self):
        """Test optional configuration settings."""
        env_vars = {
            "ACTOR_UUID": "123e4567-e89b-12d3-a456-426614174000",
            "RATE_LIMIT_PER_MINUTE": "60",
            "MAX_BODY_SIZE": "32768", 
            "LOG_LEVEL": "DEBUG"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = Config()
            assert config.RATE_LIMIT_PER_MINUTE == 60
            assert config.MAX_BODY_SIZE == 32768
            assert config.LOG_LEVEL == "DEBUG"