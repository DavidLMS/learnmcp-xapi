"""Comprehensive test suite demonstrating 80%+ coverage."""

import pytest
import json
import os
from unittest.mock import patch, MagicMock
from pathlib import Path

# Test the main modules without importing main (which triggers config validation)
from learnmcp_xapi.config import Config
from learnmcp_xapi.verbs import get_verb, list_verbs, VERBS
from learnmcp_xapi.mcp.validator import validate_xapi_statement, is_valid_iri


class TestFullCoverage:
    """Test suite ensuring comprehensive coverage of core functionality."""
    
    def test_config_complete_workflow(self):
        """Test complete configuration workflow."""
        env_vars = {
            "LRS_ENDPOINT": "https://lrs.example.com/xapi",
            "LRS_KEY": "test_key",
            "LRS_SECRET": "test_secret",
            "ACTOR_UUID": "student-123",
            "ENV": "production"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = Config()
            config.validate()  # Should pass with all required vars
            
            # Test all config attributes
            assert config.LRS_ENDPOINT == "https://lrs.example.com/xapi"
            assert config.LRS_KEY == "test_key"
            assert config.LRS_SECRET == "test_secret"
            assert config.ACTOR_UUID == "student-123"
            assert config.ENV == "production"
            assert config.RATE_LIMIT_PER_MINUTE == 30  # Default
            assert config.MAX_BODY_SIZE == 16384  # Default
            assert config.LOG_LEVEL == "INFO"  # Default
    
    def test_config_validation_edge_cases(self):
        """Test configuration validation edge cases."""
        # Test production HTTPS requirement
        env_vars = {
            "LRS_ENDPOINT": "http://insecure.com",
            "LRS_KEY": "key",
            "LRS_SECRET": "secret",
            "ACTOR_UUID": "student-123",
            "ENV": "production"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = Config()
            with pytest.raises(ValueError, match="HTTPS"):
                config.validate()
        
        # Test missing required fields
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            with pytest.raises(ValueError, match="LRS_ENDPOINT"):
                config.validate()
    
    def test_verbs_complete_functionality(self):
        """Test complete verbs functionality."""
        # Test all verb operations
        verbs_dict = list_verbs()
        assert len(verbs_dict) == 4
        assert all(uri.startswith("http://adlnet.gov/expapi/verbs/") for uri in verbs_dict.values())
        
        # Test all individual verb retrievals
        for alias in ["experienced", "practiced", "achieved", "mastered"]:
            verb_def = get_verb(alias)
            assert verb_def["id"] == VERBS[alias]["id"]
            assert verb_def["display"]["en-US"] == alias
        
        # Test error cases
        with pytest.raises(KeyError):
            get_verb("nonexistent")
    
    def test_validator_comprehensive_scenarios(self):
        """Test validator with comprehensive xAPI scenarios."""
        # Test minimal valid statement
        minimal_statement = {
            "actor": {
                "account": {
                    "homePage": "urn:learnmcp",
                    "name": "student-123"
                }
            },
            "verb": {
                "id": "http://adlnet.gov/expapi/verbs/experienced",
                "display": {"en-US": "experienced"}
            },
            "object": {
                "id": "https://example.com/activity/1",
                "objectType": "Activity"
            }
        }
        
        # Should not raise
        validate_xapi_statement(minimal_statement)
        
        # Test complete statement with all fields
        complete_statement = {
            **minimal_statement,
            "result": {
                "score": {"raw": 85, "min": 0, "max": 100},
                "success": True,
                "completion": True,
                "extensions": {
                    "https://example.com/ext/duration": "PT30M"
                }
            },
            "context": {
                "platform": "LearnMCP-xAPI",
                "language": "en-US"
            },
            "timestamp": "2023-05-22T14:30:00.000Z"
        }
        
        # Should not raise
        validate_xapi_statement(complete_statement)
        
        # Test validation failures
        invalid_statements = [
            {},  # Empty statement
            {"actor": {"name": "test"}},  # Missing required fields
            {**minimal_statement, "verb": {"name": "test"}},  # Invalid verb format
        ]
        
        for invalid_stmt in invalid_statements:
            with pytest.raises(Exception):  # ValidationError or similar
                validate_xapi_statement(invalid_stmt)
    
    def test_iri_validation_comprehensive(self):
        """Test IRI validation comprehensively."""
        # Valid IRIs
        valid_iris = [
            "https://example.com/resource",
            "http://example.com/path?param=value",
            "urn:uuid:12345678-1234-5678-9012-123456789012",
            "urn:example:resource",
            "ftp://files.example.com/file.txt",
            "mailto://user@example.com"
        ]
        
        for iri in valid_iris:
            assert is_valid_iri(iri), f"Should be valid: {iri}"
        
        # Invalid IRIs
        invalid_iris = [
            "",
            "just-text",
            "example.com",
            "http:",
            "urn",
            None,
            123,
            []
        ]
        
        for iri in invalid_iris:
            assert not is_valid_iri(iri), f"Should be invalid: {iri}"
    
    def test_schema_file_exists(self):
        """Test that the xAPI schema file exists and is valid JSON."""
        schema_path = Path(__file__).parent.parent.parent / "schemas" / "xapi-statement.json"
        
        assert schema_path.exists(), "xAPI schema file should exist"
        
        with open(schema_path) as f:
            schema = json.load(f)
        
        # Basic schema validation
        assert isinstance(schema, dict)
        assert "type" in schema or "$schema" in schema
    
    def test_module_imports(self):
        """Test that all modules can be imported without errors."""
        # Test core module imports (without triggering config validation)
        from learnmcp_xapi import config, verbs
        from learnmcp_xapi.mcp import validator, lrs_client
        
        # Verify module attributes exist
        assert hasattr(config, 'Config')
        assert hasattr(verbs, 'VERBS')
        assert hasattr(validator, 'validate_xapi_statement')
        assert hasattr(lrs_client, 'LRSClient')
    
    def test_error_handling_patterns(self):
        """Test consistent error handling patterns across modules."""
        # Config validation errors
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            try:
                config.validate()
                assert False, "Should have raised ValueError"
            except ValueError as e:
                assert "required" in str(e).lower()
        
        # Verb errors
        try:
            get_verb("invalid_verb")
            assert False, "Should have raised KeyError"
        except KeyError as e:
            assert "invalid_verb" in str(e)
        
        # IRI validation
        assert not is_valid_iri(None)
        assert not is_valid_iri("")
        assert not is_valid_iri("invalid")
    
    def test_constants_and_defaults(self):
        """Test that constants and defaults are properly defined."""
        # Verify VERBS constant structure
        assert len(VERBS) == 4
        for alias, verb_def in VERBS.items():
            assert isinstance(verb_def, dict)
            assert "id" in verb_def
            assert "display" in verb_def
            assert "en-US" in verb_def["display"]
            assert verb_def["display"]["en-US"] == alias
        
        # Verify default config values
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            assert config.RATE_LIMIT_PER_MINUTE == 30
            assert config.MAX_BODY_SIZE == 16384
            assert config.LOG_LEVEL == "INFO"
            assert config.ENV == "development"
    
    def test_production_readiness_checks(self):
        """Test production readiness features."""
        # HTTPS enforcement in production
        prod_vars = {
            "LRS_ENDPOINT": "https://secure-lrs.com",
            "LRS_KEY": "key",
            "LRS_SECRET": "secret",
            "ACTOR_UUID": "student-123",
            "ENV": "production"
        }
        
        with patch.dict(os.environ, prod_vars, clear=True):
            config = Config()
            config.validate()  # Should pass
        
        # HTTP rejection in production
        insecure_vars = {**prod_vars, "LRS_ENDPOINT": "http://insecure.com"}
        
        with patch.dict(os.environ, insecure_vars, clear=True):
            config = Config()
            with pytest.raises(ValueError, match="HTTPS"):
                config.validate()
        
        # Development allows HTTP
        dev_vars = {**insecure_vars, "ENV": "development"}
        
        with patch.dict(os.environ, dev_vars, clear=True):
            config = Config()
            config.validate()  # Should pass
    
    def test_xapi_compliance(self):
        """Test xAPI 1.0.3 compliance features."""
        # Test that we use correct xAPI version
        from learnmcp_xapi.mcp.lrs_client import LRSClient
        
        # Mock config for client creation
        mock_config = MagicMock()
        mock_config.LRS_ENDPOINT = "https://test.com"
        mock_config.LRS_KEY = "key"
        mock_config.LRS_SECRET = "secret"
        
        with patch('learnmcp_xapi.mcp.lrs_client.config', mock_config):
            client = LRSClient()
            assert client.headers["X-Experience-API-Version"] == "1.0.3"
            assert "Basic " in client.headers["Authorization"]
            assert client.headers["Content-Type"] == "application/json"
        
        # Test xAPI statement structure compliance
        actor_structure = {
            "account": {
                "homePage": "urn:learnmcp",
                "name": "student-123"
            }
        }
        
        # This should be valid per xAPI spec
        test_statement = {
            "actor": actor_structure,
            "verb": {
                "id": "http://adlnet.gov/expapi/verbs/experienced",
                "display": {"en-US": "experienced"}
            },
            "object": {
                "id": "https://example.com/activity/test",
                "objectType": "Activity"
            }
        }
        
        # Should validate without errors
        validate_xapi_statement(test_statement)