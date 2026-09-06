"""
Rail-BDMS: Application Configuration & Constants
Domain: Indian Railways Rolling Block Demand Management System
"""
from typing import List
from pydantic import BaseModel

class Settings(BaseModel):
    PROJECT_NAME: str = "Rail-BDMS"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Division Defaults (Northern Railway - Delhi Division)
    DEFAULT_DIVISION: str = "DELHI"
    DEFAULT_SECTION: str = "NZM-PWL"
    
    # Safety Invariants & Headways (in minutes)
    MIN_HEADWAY_BEFORE_MIN: int = 15  # B_before
    MIN_HEADWAY_AFTER_MIN: int = 15   # B_after
    
    # Matching Confidence Threshold
    IDENTITY_CONFIDENCE_THRESHOLD: float = 0.85
    
    # Solver Config
    SOLVER_TIMEOUT_SECONDS: int = 30
    DEFAULT_HORIZON: str = "WEEKLY"  # 26_WEEK, 4_WEEK, WEEKLY, NEXT_DAY
    
    # Weight factors for priority scoring
    WEIGHT_CRITICALITY: float = 0.55
    WEIGHT_URGENCY: float = 0.35
    WEIGHT_SHADOW_OPPORTUNITY: float = 0.10
    
    # Host and Port
    HOST: str = "0.0.0.0"
    PORT: int = 8000

settings = Settings()
