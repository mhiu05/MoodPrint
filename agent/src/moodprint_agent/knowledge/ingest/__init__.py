"""Ingestion package. Importing it does not open a database connection."""

from moodprint_agent.knowledge.ingest.cli import main

__all__ = ["main"]
