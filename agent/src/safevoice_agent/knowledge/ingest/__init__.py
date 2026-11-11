"""Ingestion package. Importing it does not open a database connection."""

from safevoice_agent.knowledge.ingest.cli import main

__all__ = ["main"]
