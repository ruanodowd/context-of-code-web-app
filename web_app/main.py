from fastapi import FastAPI, Depends, HTTPException, Request, Security
from fastapi.security.api_key import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta
from typing import List
import uvicorn

from .database import get_db
from .models import Metric, MetricType
from .schemas import (
    MetricCreate, MetricBulkCreate, Metric as MetricSchema,
    MetricType as MetricTypeSchema, MetricTypeCreate
)
from .config import get_settings

settings = get_settings()

app = FastAPI(
    title="Metrics Dashboard",
    description="A modern FastAPI dashboard for tracking various metrics",
    version="1.0.0",
    debug=settings.DEBUG
)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Key security
api_key_header = APIKeyHeader(name="X-API-Key")

async def get_api_key(api_key: str = Security(api_key_header)):
    if api_key != settings.API_KEY:
        raise HTTPException(
            status_code=403,
            detail="Could not validate API key"
        )
    return api_key

# Mount static files directory
app.mount("/static", StaticFiles(directory="web_app/static"), name="static")

# Setup Jinja2 templates with datetime filter
templates = Jinja2Templates(directory="web_app/templates")

# Add custom filters to Jinja2 environment
def format_datetime(value, format='%Y-%m-%d %H:%M:%S'):
    if value is None:
        return ''
    return value.strftime(format)

templates.env.filters['strftime'] = format_datetime

@app.post("/api/metric-types/", response_model=MetricTypeSchema)
async def create_metric_type(
    metric_type: MetricTypeCreate,
    db: AsyncSession = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """Create a new metric type definition."""
    db_metric_type = MetricType(**metric_type.model_dump())
    db.add(db_metric_type)
    await db.commit()
    await db.refresh(db_metric_type)
    return db_metric_type

@app.get("/api/metric-types/", response_model=List[MetricTypeSchema])
async def list_metric_types(db: AsyncSession = Depends(get_db)):
    """List all available metric types."""
    result = await db.execute(select(MetricType))
    return result.scalars().all()

@app.post("/api/metrics/", response_model=MetricSchema)
async def create_metric(
    metric: MetricCreate,
    db: AsyncSession = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """Create a new metric measurement."""
    # Verify metric type exists
    result = await db.execute(
        select(MetricType).where(MetricType.id == metric.metric_type_id)
    )
    metric_type = result.scalar_one_or_none()
    if not metric_type:
        raise HTTPException(status_code=404, detail="Metric type not found")

    # Create the metric
    db_metric = Metric(**metric.model_dump())
    db.add(db_metric)
    await db.commit()
    
    # Refresh with metric_type relationship loaded
    result = await db.execute(
        select(Metric)
        .options(selectinload(Metric.metric_type))
        .where(Metric.id == db_metric.id)
    )
    return result.scalar_one()

@app.post("/api/metrics/bulk", response_model=List[MetricSchema])
async def create_metrics_bulk(
    metrics: MetricBulkCreate,
    db: AsyncSession = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """Bulk create multiple metric measurements."""
    # Verify all metric types exist
    metric_type_ids = {m.metric_type_id for m in metrics.metrics}
    result = await db.execute(
        select(MetricType).where(MetricType.id.in_(metric_type_ids))
    )
    found_types = {mt.id for mt in result.scalars().all()}
    missing_types = metric_type_ids - found_types
    if missing_types:
        raise HTTPException(
            status_code=404,
            detail=f"Metric types not found: {missing_types}"
        )

    db_metrics = [Metric(**m.model_dump()) for m in metrics.metrics]
    db.add_all(db_metrics)
    await db.commit()
    
    # Refresh all metrics to get their IDs
    for metric in db_metrics:
        await db.refresh(metric)
    
    return db_metrics

@app.get("/api/metrics/", response_model=List[MetricSchema])
async def get_metrics(db: AsyncSession = Depends(get_db)):
    """
    Retrieve all metrics.
    Returns a list of all metrics in the database.
    """
    result = await db.execute(select(Metric))
    metrics = result.scalars().all()
    return metrics

@app.get("/api/metrics/{metric_name}")
async def get_metric_by_name(metric_name: str, db: AsyncSession = Depends(get_db)):
    """
    Retrieve metrics by name.
    Returns the latest value for a specific metric.
    """
    result = await db.execute(
        select(Metric)
        .filter(Metric.name == metric_name)
        .order_by(Metric.timestamp.desc())
        .limit(1)
    )
    metric = result.scalar_one_or_none()
    if metric is None:
        raise HTTPException(status_code=404, detail="Metric not found")
    return metric

@app.get("/")
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Main dashboard view.
    Renders the dashboard template with metric types and their history.
    """
    # Get all metric types
    result = await db.execute(
        select(MetricType)
        .order_by(MetricType.name)
    )
    metric_types = result.scalars().all()

    # Get historical data for each metric type
    metric_history = {}
    for metric_type in metric_types:
        result = await db.execute(
            select(Metric)
            .options(selectinload(Metric.metric_type))
            .filter(Metric.metric_type_id == metric_type.id)
            .order_by(Metric.recorded_at.desc())
            .limit(50)  # Limit to last 50 measurements for performance
        )
        metrics = result.scalars().all()
        if metrics:
            # Convert SQLAlchemy models to dictionaries for JSON serialization
            # Convert metrics to a serializable format
            serialized_metrics = []
            for metric in metrics:
                metric_dict = {
                    'id': metric.id,
                    'value': metric.value,
                    'recorded_at': metric.recorded_at.isoformat() if metric.recorded_at else None,
                    'source': metric.source,
                    'metric_metadata': metric.metric_metadata,
                    'metric_type_id': metric.metric_type_id
                }
                serialized_metrics.append(metric_dict)
            metric_history[metric_type.id] = serialized_metrics

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "metric_types": metric_types,
            "metric_history": metric_history,
            "settings": settings
        }
    )

if __name__ == "__main__":
    uvicorn.run("web_app.main:app", host="0.0.0.0", port=8000, reload=True)
