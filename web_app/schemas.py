from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict

class MetricTypeBase(BaseModel):
    """Base schema for metric types."""
    name: str = Field(..., description="Unique identifier for the metric type")
    description: Optional[str] = Field(None, description="Detailed description of what this metric represents")
    unit: Optional[str] = Field(None, description="Unit of measurement (e.g., '%', 'MB', 'requests/sec')")

class MetricTypeCreate(MetricTypeBase):
    """Schema for creating a new metric type."""
    pass

class MetricType(MetricTypeBase):
    """Schema for reading a metric type."""
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class MetricCreate(BaseModel):
    """Schema for creating a new metric."""
    metric_type_id: int = Field(..., description="ID of the metric type")
    value: float = Field(..., description="Numerical value of the metric")
    recorded_at: Optional[datetime] = Field(None, description="When the metric was recorded")
    source: Optional[str] = Field(None, description="Origin of the metric (e.g., 'server1', 'process2')")
    metric_metadata: Optional[Dict] = Field(default_factory=dict, description="Additional JSON data associated with the measurement")

class Metric(BaseModel):
    """Schema for reading a metric."""
    id: int
    metric_type_id: int
    value: float
    recorded_at: datetime
    source: Optional[str]
    metric_metadata: Optional[Dict]
    metric_type: MetricType

    class Config:
        from_attributes = True

class MetricBulkCreate(BaseModel):
    """Schema for bulk creating metrics."""
    metrics: List[MetricCreate] = Field(..., description="List of metrics to create")
