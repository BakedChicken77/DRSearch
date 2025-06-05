from pydantic import BaseModel
from typing import List, Optional

class Config(BaseModel):
    port: int

class RemovePointsRequest(BaseModel):
    selected_ids: List[str]

class Settings(BaseModel):
    setting1: Optional[str] = None
    setting2: Optional[str] = None
    setting3: Optional[str] = None
    setting4: Optional[str] = None
    setting5: Optional[str] = None
