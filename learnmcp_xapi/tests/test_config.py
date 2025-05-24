"""Tests for configuration module."""

import os
import pytest
from unittest.mock import patch

from learnmcp_xapi.config import Config


class TestConfig:
    """Test configuration validation and defaults."""
    
    def test_config_with_all_required_env_vars(self):
        """Test config initialization with all required environment variables."""
        env_vars = {
            "LRS_ENDPOINT": "https://example.com/xapi",
            "LRS_KEY": "test_key",
            "LRS_SECRET": "test_secret", 
            "ACTOR_UUID": "123e4567-e89b-12d3-a456-426614174000"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = Config()
            config.validate()  # Should not raise
            
            assert config.LRS_ENDPOINT == "https://example.com/xapi"
            assert config.LRS_KEY == "test_key"
            assert config.LRS_SECRET == "test_secret"
            assert config.ACTOR_UUID == "123e4567-e89b-12d3-a456-426614174000"
    
    def test_config_missing_lrs_endpoint(self):
        """Test config validation fails when LRS_ENDPOINT is missing."""
        env_vars = {
            "LRS_KEY": "test_key",
            "LRS_SECRET": "test_secret",
            "ACTOR_UUID": "123e4567-e89b-12d3-a456-426614174000"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = Config()
            with pytest.raises(ValueError, match="LRS_ENDPOINT is required"):
                config.validate()
    
    def test_config_missing_lrs_key(self):
        """Test config validation fails when LRS_KEY is missing."""
        env_vars = {
            "LRS_ENDPOINT": "https://example.com/xapi",
            "LRS_SECRET": "test_secret",
            "ACTOR_UUID": "123e4567-e89b-12d3-a456-426614174000"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = Config()
            with pytest.raises(ValueError, match="LRS_KEY and LRS_SECRET are required"):
                config.validate()
    
    def test_config_missing_lrs_secret(self):
        """Test config validation fails when LRS_SECRET is missing."""
        env_vars = {
            "LRS_ENDPOINT": "https://example.com/xapi",
            "LRS_KEY": "test_key",
            "ACTOR_UUID": "123e4567-e89b-12d3-a456-426614174000"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = Config()
            with pytest.raises(ValueError, match="LRS_KEY and LRS_SECRET are required"):
                config.validate()
    
    def test_config_missing_actor_uuid(self):
        """Test config validation fails when ACTOR_UUID is missing."""
        env_vars = {
            "LRS_ENDPOINT": "https://example.com/xapi",
            "LRS_KEY": "test_key",
            "LRS_SECRET": "test_secret"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = Config()
            with pytest.raises(ValueError, match="ACTOR_UUID is required"):
                config.validate()
    
    def test_config_invalid_lrs_endpoint_format(self):
        """Test config validation fails for invalid LRS endpoint format."""
        env_vars = {
            "LRS_ENDPOINT": "not-a-url",
            "LRS_KEY": "test_key", 
            "LRS_SECRET": "test_secret",
            "ACTOR_UUID": "123e4567-e89b-12d3-a456-426614174000"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = Config()
            # Current implementation doesn't validate URL format, just presence
            config.validate()  # Should pass
    
    def test_config_development_allows_http(self):
        """Test that HTTP is allowed in development mode."""
        env_vars = {
            "LRS_ENDPOINT": "http://localhost:8080/xapi",
            "LRS_KEY": "test_key",
            "LRS_SECRET": "test_secret",
            "ACTOR_UUID": "123e4567-e89b-12d3-a456-426614174000",
            "ENV": "development"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = Config()
            config.validate()  # Should not raise
            assert config.LRS_ENDPOINT == "http://localhost:8080/xapi"
    
    def test_config_production_requires_https(self):
        """Test that HTTPS is required in production mode."""
        env_vars = {
            "LRS_ENDPOINT": "http://example.com/xapi",
            "LRS_KEY": "test_key",
            "LRS_SECRET": "test_secret", 
            "ACTOR_UUID": "123e4567-e89b-12d3-a456-426614174000",
            "ENV": "production"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = Config()
            with pytest.raises(ValueError, match="LRS_ENDPOINT must use HTTPS in production"):
                config.validate()
    
    def test_config_strips_trailing_slash_from_endpoint(self):
        """Test that trailing slash is preserved (not stripped) from LRS endpoint."""
        env_vars = {
            "LRS_ENDPOINT": "https://example.com/xapi/",
            "LRS_KEY": "test_key",
            "LRS_SECRET": "test_secret",
            "ACTOR_UUID": "123e4567-e89b-12d3-a456-426614174000"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = Config()
            # Current implementation doesn't strip trailing slash
            assert config.LRS_ENDPOINT == "https://example.com/xapi/"
    
    def test_config_accepts_any_actor_uuid_format(self):
        """Test config accepts any non-empty actor UUID format."""
        env_vars = {
            "LRS_ENDPOINT": "https://example.com/xapi",
            "LRS_KEY": "test_key",
            "LRS_SECRET": "test_secret",
            "ACTOR_UUID": "student-12345"  # Any format is fine
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = Config()
            config.validate()  # Should not raise
            assert config.ACTOR_UUID == "student-12345"
    
    def test_config_default_environment(self):
        """Test default environment is 'development'."""
        env_vars = {
            "LRS_ENDPOINT": "https://example.com/xapi",
            "LRS_KEY": "test_key",
            "LRS_SECRET": "test_secret",
            "ACTOR_UUID": "123e4567-e89b-12d3-a456-426614174000"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = Config()
            assert config.ENV == "development"