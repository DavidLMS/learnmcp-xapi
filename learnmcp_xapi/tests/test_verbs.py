"""Tests for verbs module."""

import pytest

from learnmcp_xapi.verbs import get_verb, list_verbs, VERBS


class TestVerbs:
    """Test verb mapping functionality."""
    
    def test_list_verbs_returns_all_verbs(self):
        """Test that list_verbs returns all defined verbs."""
        verbs = list_verbs()
        
        assert isinstance(verbs, dict)
        assert len(verbs) == 4
        assert "experienced" in verbs
        assert "practiced" in verbs
        assert "achieved" in verbs
        assert "mastered" in verbs
    
    def test_list_verbs_returns_correct_uris(self):
        """Test that list_verbs returns correct ADL verb URIs."""
        verbs = list_verbs()
        
        assert verbs["experienced"] == "http://adlnet.gov/expapi/verbs/experienced"
        assert verbs["practiced"] == "http://adlnet.gov/expapi/verbs/practiced"
        assert verbs["achieved"] == "http://adlnet.gov/expapi/verbs/achieved"
        assert verbs["mastered"] == "http://adlnet.gov/expapi/verbs/mastered"
    
    def test_get_verb_returns_correct_definition(self):
        """Test that get_verb returns correct verb definition."""
        verb_def = get_verb("experienced")
        
        assert isinstance(verb_def, dict)
        assert verb_def["id"] == "http://adlnet.gov/expapi/verbs/experienced"
        assert verb_def["display"]["en-US"] == "experienced"
    
    def test_get_verb_all_defined_verbs(self):
        """Test get_verb for all defined verbs."""
        for alias in VERBS.keys():
            verb_def = get_verb(alias)
            
            assert verb_def["id"] == VERBS[alias]["id"]
            assert verb_def["display"]["en-US"] == alias
    
    def test_get_verb_unknown_verb_raises_keyerror(self):
        """Test that get_verb raises KeyError for unknown verb."""
        with pytest.raises(KeyError, match="unknown_verb"):
            get_verb("unknown_verb")
    
    def test_get_verb_empty_string_raises_keyerror(self):
        """Test that get_verb raises KeyError for empty string."""
        with pytest.raises(KeyError):
            get_verb("")
    
    def test_get_verb_none_raises_keyerror(self):
        """Test that get_verb raises appropriate error for None."""
        with pytest.raises((KeyError, TypeError)):
            get_verb(None)
    
    def test_verbs_constant_immutable(self):
        """Test that VERBS constant contains expected values."""
        expected_verbs = {
            "experienced": {
                "id": "http://adlnet.gov/expapi/verbs/experienced",
                "display": {"en-US": "experienced"}
            },
            "practiced": {
                "id": "http://adlnet.gov/expapi/verbs/practiced", 
                "display": {"en-US": "practiced"}
            },
            "achieved": {
                "id": "http://adlnet.gov/expapi/verbs/achieved",
                "display": {"en-US": "achieved"}
            },
            "mastered": {
                "id": "http://adlnet.gov/expapi/verbs/mastered",
                "display": {"en-US": "mastered"}
            }
        }
        
        assert VERBS == expected_verbs
    
    def test_verb_uris_are_valid_adl_format(self):
        """Test that all verb URIs follow ADL format."""
        for alias, verb_def in VERBS.items():
            uri = verb_def["id"]
            assert uri.startswith("http://adlnet.gov/expapi/verbs/")
            assert uri.endswith(alias)
    
    def test_verb_aliases_are_lowercase(self):
        """Test that all verb aliases are lowercase."""
        for alias in VERBS.keys():
            assert alias.islower()
            assert " " not in alias
            assert alias.isalpha()