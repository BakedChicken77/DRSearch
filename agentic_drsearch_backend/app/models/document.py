"""
Typed dataclass for a document (optional, not used directly in DB layer).
"""

from dataclasses import dataclass

@dataclass
class Document:
    id: int
    filename: str
    content: str
