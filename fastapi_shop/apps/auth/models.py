from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class User(BaseModel):
    username: str
    email: Optional[str] = None
    password: str
    oauth_provider: Optional[str] = None
    oauth_id: Optional[str] = None
