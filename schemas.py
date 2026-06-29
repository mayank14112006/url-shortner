from pydantic import BaseModel, Field, HttpUrl
from typing import Optional
from datetime import datetime

# --- User Schemas ---

class UserBase(BaseModel):
    email: str

class UserCreate(UserBase):
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters long")

class UserOut(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    user_id: Optional[int] = None
    email: Optional[str] = None


# --- URL Schemas ---

class URLCreate(BaseModel):
    original_url: str = Field(..., description="The original URL to be shortened")
    expires_at: Optional[datetime] = Field(None, description="Optional expiry timestamp for the short URL")


class URLOut(BaseModel):
    id: int
    original_url: str
    short_code: Optional[str]
    short_url: str  # Fully qualified shortened URL (e.g. http://localhost:8000/r/abc123)
    clicks: int
    created_at: datetime
    expires_at: Optional[datetime]
    user_id: int

    class Config:
        from_attributes = True
