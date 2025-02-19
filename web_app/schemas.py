from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List

class MetricBase(BaseModel):
    """Base Pydantic model for metric data validation."""
    name: str = Field(..., description="Name of the metric")
    value: float = Field(..., description="Numerical value of the metric")
    unit: str = Field(..., description="Unit of measurement")

class MetricCreate(MetricBase):
    """Pydantic model for creating a single metric."""
    timestamp: Optional[datetime] = Field(None, description="Optional timestamp for the metric. If not provided, current time will be used.")

class MetricBulkCreate(BaseModel):
    """Pydantic model for bulk metric creation."""
    metrics: List[MetricCreate] = Field(..., description="List of metrics to create")

class Metric(MetricBase):
    """Pydantic model for returning metrics, including database fields."""
    id: int
    timestamp: datetime

    class Config:
        """Configure Pydantic to work with SQLAlchemy models."""
        from_attributes = True
