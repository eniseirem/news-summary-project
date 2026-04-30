"""
api/schemas.py
==============
Shared Pydantic models for API requests and responses.
"""

from pydantic import BaseModel
from typing import Optional


class Article(BaseModel):
    """Article model used across multiple endpoints."""
    id: str
    title: str
    body: str
    language: str

    # Newly Added fields
    original_language: Optional[str] = None

    source: Optional[str] = None
    published_at: Optional[str] = None

