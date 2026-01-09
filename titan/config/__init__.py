"""Configuration package - uses varlord for config management.

IMPORTANT: All configuration models are defined in models.py.
No module should define its own config model.
All modules access the same TitanConfig model for type safety.
"""

from titan.config.loader import ConfigLoader
from titan.config.models import TitanConfig

__all__ = ["ConfigLoader", "TitanConfig"]
