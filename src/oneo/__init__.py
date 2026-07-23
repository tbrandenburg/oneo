"""Oneo: OKF-to-Neo4j multi-corpus graph retrieval."""

from importlib.metadata import version

from oneo.cli import main

__version__ = version("oneo")

__all__ = ["__version__", "main"]
