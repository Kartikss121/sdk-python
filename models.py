from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime

class UserUsage(BaseModel):
    model_config = ConfigDict(extra='ignore', populate_by_name=True)
    
    user_id: str
    date: str # ISO format YYYY-MM-DD
    count: int = Field(default=0, ge=0)

class UserData(BaseModel):
    model_config = ConfigDict(extra='ignore', populate_by_name=True)
    
    user_id: str
    email: Optional[str] = None
    credits: int = Field(default=0, ge=0)
    plan: str = "free" # "free", "pro", etc.
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Ad Tracking Limits
    ads_watched_today: int = Field(default=0, ge=0)
    ad_credits_earned_today: int = Field(default=0, ge=0)
    last_ad_date: Optional[str] = None # YYYY-MM-DD
