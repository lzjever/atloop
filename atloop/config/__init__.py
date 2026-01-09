"""Configuration package - uses varlord for config management.

IMPORTANT: All configuration models are defined in models.py.
No module should define its own config model.
All modules access the same AtloopConfig model for type safety.
"""

from atloop.config.loader import ConfigLoader
from atloop.config.models import AtloopConfig

__all__ = ["ConfigLoader", "AtloopConfig"]
