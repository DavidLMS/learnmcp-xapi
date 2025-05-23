"""xAPI verbs mapping - alias to official URI."""

from typing import Dict

VERBS: Dict[str, Dict[str, str]] = {
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


def get_verb(alias: str) -> Dict[str, str]:
    """Get verb definition by alias.
    
    Args:
        alias: Verb alias (e.g., 'practiced')
        
    Returns:
        Verb definition with id and display
        
    Raises:
        KeyError: If alias is not found
    """
    if alias not in VERBS:
        raise KeyError(f"Unknown verb alias: {alias}")
    return VERBS[alias]


def list_verbs() -> Dict[str, str]:
    """List all available verb aliases and their URIs.
    
    Returns:
        Dict mapping alias to URI
    """
    return {alias: verb["id"] for alias, verb in VERBS.items()}