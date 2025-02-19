from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON, func
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()

class MetricType(Base):
    """Model for storing metric type definitions.
    
    This model defines the types of metrics that can be stored:
    - name: Unique identifier for the metric type (e.g., 'cpu_usage', 'memory_usage')
    - description: Detailed description of what this metric represents
    - unit: The unit of measurement (e.g., '%', 'MB', 'requests/sec')
    - created_at: When this metric type was defined
    """
    __tablename__ = "metric_types"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text)
    unit = Column(String(50))
    created_at = Column(DateTime, default=func.now())

    # Relationship
    metrics = relationship("Metric", back_populates="metric_type", cascade="all, delete")

class Metric(Base):
    """Model for storing metric values.
    
    This model stores the actual metric measurements:
    - metric_type_id: Reference to the metric type definition
    - value: The numerical value of the metric
    - recorded_at: When the metric was recorded
    - source: Origin of the metric (e.g., 'server1', 'process2')
    - metadata: Additional JSON data associated with the measurement
    """
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, index=True)
    metric_type_id = Column(Integer, ForeignKey("metric_types.id", ondelete="CASCADE"), nullable=False)
    value = Column(Float, nullable=False)
    recorded_at = Column(DateTime, default=func.now(), index=True)
    source = Column(String(255))
    metric_metadata = Column(JSON)

    # Relationship
    metric_type = relationship("MetricType", back_populates="metrics")

    @classmethod
    def from_schema(cls, metric_data):
        """Create a Metric instance from a Pydantic schema."""
        return cls(
            name=metric_data.name,
            value=metric_data.value,
            unit=metric_data.unit,
            timestamp=metric_data.timestamp or datetime.utcnow()
        )

    def to_dict(self):
        """Convert the model instance to a dictionary for API responses."""
        return {
            "id": self.id,
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "timestamp": self.timestamp.isoformat()
        }
