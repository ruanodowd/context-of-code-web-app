from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class MetricBase(BaseModel):
    """Base Pydantic model for metric data validation."""
    name: str
    value: float
    unit: str

class MetricCreate(MetricBase):
    """Pydantic model for creating new metrics."""
    pass

class Metric(MetricBase):
    """Pydantic model for returning metrics, including database fields."""
    id: int
    timestamp: datetime

    class Config:
        """Configure Pydantic to work with SQLAlchemy models."""
        from_attributes = True
