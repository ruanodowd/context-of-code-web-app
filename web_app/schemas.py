from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime
from typing import Optional, List
from uuid import UUID


class UnitBase(BaseModel):
    """Base schema for units."""
    name: str = Field(..., description="Name of the unit (e.g., 'Percentage', 'Megabytes')")
    symbol: str = Field(..., description="Symbol or abbreviation (e.g., '%', 'MB')")
    description: Optional[str] = Field(None, description="Optional description of the unit")

    @field_validator('name', 'symbol')
    @classmethod
    def validate_fields(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError("Field cannot be empty")
        return v.strip()


class UnitCreate(UnitBase):
    """Schema for creating a new unit."""
    pass


class Unit(UnitBase):
    """Schema for reading a unit."""
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

class MetricTypeBase(BaseModel):
    """Base schema for metric types."""
    name: str = Field(..., description="Unique identifier for the metric type")
    description: Optional[str] = Field(None, description="Detailed description of what this metric represents")
    unit_id: UUID = Field(..., description="ID of the unit of measurement")
    is_active: bool = Field(True, description="Whether this metric type is currently active")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError("Metric type name cannot be empty")
        return v.strip()

class MetricTypeCreate(MetricTypeBase):
    """Schema for creating a new metric type."""
    pass

class MetricType(MetricTypeBase):
    """Schema for reading a metric type."""
    id: UUID
    created_at: datetime
    unit: Unit

    class Config:
        from_attributes = True

class SourceBase(BaseModel):
    """Base schema for metric sources."""
    name: str = Field(..., description="Name of the source")
    description: Optional[str] = Field(None, description="Detailed description of the source")
    ip_address: Optional[str] = Field(None, description="IP address of the source")
    is_active: bool = Field(True, description="Whether this source is currently active")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError("Source name cannot be empty")
        return v.strip()
    
    @field_validator('ip_address')
    @classmethod
    def validate_ip_address(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        # Basic validation for IPv4 and IPv6
        if len(v) > 0 and not any([
            # IPv4 validation (simple check)
            all(o.isdigit() and int(o) < 256 for o in v.split('.')) if '.' in v else False,
            # IPv6 validation (simple check)
            all(all(c in '0123456789abcdefABCDEF:' for c in p) for p in v.split(':')) if ':' in v else False
        ]):
            raise ValueError("Invalid IP address format")
        return v

class SourceCreate(SourceBase):
    """Schema for creating a new source."""
    pass

class Source(SourceBase):
    """Schema for reading a source."""
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

class MetadataCreate(BaseModel):
    """Schema for creating metadata for a metric."""
    key: str = Field(..., description="Metadata key")
    value: str = Field(..., description="Metadata value")
    
    @field_validator('key')
    @classmethod
    def validate_key(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError("Metadata key cannot be empty")
        return v.strip()

class Metadata(MetadataCreate):
    """Schema for reading metadata."""
    id: UUID
    created_at: datetime
    
    class Config:
        from_attributes = True

class MetricCreate(BaseModel):
    """Schema for creating a new metric."""
    metric_type_id: Optional[UUID] = Field(None, description="ID of the metric type")
    metric_type_name: Optional[str] = Field(None, description="Name of the metric type")
    source_id: Optional[UUID] = Field(None, description="ID of the source")
    source_name: Optional[str] = Field(None, description="Name of the source")
    value: float = Field(..., description="Numerical value of the metric")
    recorded_at: Optional[datetime] = Field(None, description="When the metric was recorded")
    metadata: Optional[List[MetadataCreate]] = Field(default_factory=list, description="Additional metadata associated with the measurement")
    
    @model_validator(mode='after')
    def validate_metric_type_and_source(self) -> 'MetricCreate':
        if not self.metric_type_id and not self.metric_type_name:
            raise ValueError("Either metric_type_id or metric_type_name must be provided")
        if self.metric_type_id and self.metric_type_name:
            raise ValueError("Only one of metric_type_id or metric_type_name should be provided")
        if not self.source_id and not self.source_name:
            raise ValueError("Either source_id or source_name must be provided")
        if self.source_id and self.source_name:
            raise ValueError("Only one of source_id or source_name should be provided")
        return self
    
    @field_validator('value')
    @classmethod
    def validate_value(cls, v: float) -> float:
        if v is None:
            raise ValueError("Metric value cannot be None")
        return float(v)

class Metric(BaseModel):
    """Schema for reading a metric."""
    id: UUID
    metric_type_id: UUID
    source_id: UUID
    value: float
    recorded_at: datetime
    metric_metadata_items: Optional[List[Metadata]] = None
    metric_type: MetricType
    source: Source

    class Config:
        from_attributes = True

class MetricBulkCreate(BaseModel):
    """Schema for bulk creating metrics."""
    metrics: List[MetricCreate] = Field(..., description="List of metrics to create")
    
    @model_validator(mode='after')
    def validate_metrics(self) -> 'MetricBulkCreate':
        if not self.metrics or len(self.metrics) == 0:
            raise ValueError("At least one metric must be provided")
        return self
