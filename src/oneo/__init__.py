"""Oneo: OKF-to-Neo4j graph retrieval proof of concept."""

from importlib.metadata import version

from oneo.cli import main

__version__ = version("oneo")

__all__ = ["__version__", "main"]
