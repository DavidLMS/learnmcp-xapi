"""xAPI statement validation using JSON Schema."""

import json
import pathlib
from typing import Dict, Any

from jsonschema import Draft7Validator

# Load xAPI statement schema at module level
_SCHEMA_PATH = pathlib.Path(__file__).parent.parent.parent / "schemas" / "xapi-statement.json"
_STATEMENT_SCHEMA = json.loads(_SCHEMA_PATH.read_text())
_validator = Draft7Validator(_STATEMENT_SCHEMA)


def validate_xapi_statement(statement: Dict[str, Any]) -> None:
    """Validate xAPI statement against official schema.
    
    Args:
        statement: xAPI statement dictionary
        
    Raises:
        ValidationError: If statement doesn't conform to xAPI 1.0.3 schema
    """
    _validator.validate(statement)


def is_valid_iri(iri: str) -> bool:
    """Check if string is a valid IRI (simplified check).
    
    Args:
        iri: String to validate as IRI
        
    Returns:
        True if valid IRI format
    """
    return (
        isinstance(iri, str) 
        and len(iri) > 0
        and ("://" in iri or iri.startswith("urn:"))
    )