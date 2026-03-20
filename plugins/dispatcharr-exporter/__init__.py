"""
Dispatcharr Prometheus Exporter Plugin

This package provides Prometheus-compatible metrics exposition for Dispatcharr.
"""

from .plugin import Plugin, PLUGIN_CONFIG

__version__ = PLUGIN_CONFIG["version"]
__all__ = ["Plugin"]
