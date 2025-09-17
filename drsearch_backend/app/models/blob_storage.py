from pydantic import BaseModel
from typing import List, Optional

class ElementMetadata(BaseModel):
    filepath: Optional[str] = None
    image_base64: Optional[List[str]] = None
    category: Optional[str] = None
    document_title: Optional[str] = None
    filename: Optional[str] = None
    text_as_html: Optional[str] = None
    url: Optional[str] = None
    embedding: Optional[List[float]] = None
    images: Optional[List[str]] = None

    class Config:
        extra = "allow"


class Element(BaseModel):
    page_content: str | None = None
    metadata: ElementMetadata

    class Config:
        extra = "allow"
