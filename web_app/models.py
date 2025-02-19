from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Metric(Base):
    """
    Base model for storing metrics.
    
    This model is designed to be flexible and store various types of metrics:
    - name: The identifier of the metric (e.g., 'cpu_usage', 'memory_usage')
    - value: The numerical value of the metric
    - unit: The unit of measurement (e.g., '%', 'MB', 'requests/sec')
    - timestamp: When the metric was recorded
    """
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    value = Column(Float)
    unit = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        """Convert the model instance to a dictionary for API responses."""
        return {
            "id": self.id,
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "timestamp": self.timestamp.isoformat()
        }
