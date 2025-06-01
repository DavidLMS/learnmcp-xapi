"""LRS Plugins for learnmcp-xapi."""

from .base import LRSPlugin, LRSPluginConfig
from .registry import plugin_registry
from .factory import PluginFactory

__all__ = ["LRSPlugin", "LRSPluginConfig", "plugin_registry", "PluginFactory"]