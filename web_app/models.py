from datetime import datetime
import uuid
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text, JSON, func, Boolean, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.declarative import declarative_base
from typing import Optional


Base = declarative_base()

class Unit(Base):
    """Model for storing measurement units.
    
    This model defines the units that can be used for metrics:
    - id: UUID primary key for security
    - name: Name of the unit (e.g., 'Percentage', 'Megabytes')
    - symbol: Symbol or abbreviation (e.g., '%', 'MB')
    - description: Optional description of the unit
    - created_at: When this unit was defined
    """
    __tablename__ = "units"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(255), unique=True, nullable=False)
    symbol = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=func.now())

    # Relationship
    metric_types = relationship("MetricType", back_populates="unit")

    @validates('name', 'symbol')
    def validate_fields(self, key, value):
        if not value or len(value.strip()) == 0:
            raise ValueError(f"Unit {key} cannot be empty")
        return value.strip()


class MetricType(Base):
    """Model for storing metric type definitions.
    
    This model defines the types of metrics that can be stored:
    - id: UUID primary key for security
    - name: Unique identifier for the metric type (e.g., 'cpu_usage', 'memory_usage')
    - description: Detailed description of what this metric represents
    - unit_id: Foreign key reference to the unit of measurement
    - created_at: When this metric type was defined
    - is_active: Whether this metric type is currently active
    """
    __tablename__ = "metric_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("units.id"), nullable=False)
    created_at = Column(DateTime, default=func.now())
    is_active = Column(Boolean, default=True)

    # Relationships
    unit = relationship("Unit", back_populates="metric_types")
    metrics = relationship("Metric", back_populates="metric_type", cascade="all, delete")
    
    @validates('name')
    def validate_name(self, key, name):
        if not name or len(name.strip()) == 0:
            raise ValueError("Metric type name cannot be empty")
        return name.strip()

class Source(Base):
    """Model for storing metric sources.
    
    This model defines the sources from which metrics are collected:
    - id: UUID primary key for security
    - name: Name of the source (e.g., 'server1', 'process2')
    - description: Detailed description of the source
    - ip_address: IP address of the source (optional)
    - created_at: When this source was defined
    - is_active: Whether this source is currently active
    """
    __tablename__ = "sources"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text)
    ip_address = Column(String(45))  # IPv6 compatible
    created_at = Column(DateTime, default=func.now())
    is_active = Column(Boolean, default=True)
    
    # Relationship
    metrics = relationship("Metric", back_populates="source")
    
    @validates('name')
    def validate_name(self, key, name):
        if not name or len(name.strip()) == 0:
            raise ValueError("Source name cannot be empty")
        return name.strip()
    
    @validates('ip_address')
    def validate_ip_address(self, key, ip_address):
        if ip_address is None:
            return None
        ip_address = ip_address.strip()
        # Basic validation for IPv4 and IPv6
        if len(ip_address) > 0 and not any([
            # IPv4 validation (simple check)
            all(o.isdigit() and int(o) < 256 for o in ip_address.split('.')) if '.' in ip_address else False,
            # IPv6 validation (simple check)
            all(all(c in '0123456789abcdefABCDEF:' for c in p) for p in ip_address.split(':')) if ':' in ip_address else False
        ]):
            raise ValueError("Invalid IP address format")
        return ip_address

class Metric(Base):
    """Model for storing metric values.
    
    This model stores the actual metric measurements:
    - id: UUID primary key for security
    - metric_type_id: Reference to the metric type definition
    - source_id: Reference to the source definition
    - value: The numerical value of the metric
    - recorded_at: When the metric was recorded
    """
    __tablename__ = "metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    metric_type_id = Column(UUID(as_uuid=True), ForeignKey("metric_types.id", ondelete="CASCADE"), nullable=False)
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.id"), nullable=False)
    value = Column(Float, nullable=False)
    recorded_at = Column(DateTime, default=func.now(), index=True)

    # Relationships
    metric_type = relationship("MetricType", back_populates="metrics")
    source = relationship("Source", back_populates="metrics")
    metric_metadata_items = relationship("MetricMetadata", back_populates="metric", cascade="all, delete")
    
    @validates('value')
    def validate_value(self, key, value):
        if value is None:
            raise ValueError("Metric value cannot be None")
        return float(value)

class MetricMetadata(Base):
    """Model for storing metric metadata.
    
    This model stores additional metadata associated with metrics:
    - id: UUID primary key for security
    - metric_id: Reference to the metric
    - key: Metadata key
    - value: Metadata value
    - created_at: When this metadata was created
    """
    __tablename__ = "metric_metadata"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    metric_id = Column(UUID(as_uuid=True), ForeignKey("metrics.id", ondelete="CASCADE"), nullable=False)
    key = Column(String(255), nullable=False)
    value = Column(Text)
    created_at = Column(DateTime, default=func.now())
    
    # Relationship
    metric = relationship("Metric", back_populates="metric_metadata_items")
    
    __table_args__ = (
        UniqueConstraint('metric_id', 'key', name='unique_metadata_key_per_metric'),
    )
    
    @validates('key')
    def validate_key(self, key, value):
        if not value or len(value.strip()) == 0:
            raise ValueError("Metadata key cannot be empty")
        return value.strip()
