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
from .models import Metric
from .schemas import MetricCreate, MetricBulkCreate, Metric as MetricSchema
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
    allow_origins=settings.CORS_ORIGINS,
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

# Setup Jinja2 templates
templates = Jinja2Templates(directory="web_app/templates")

@app.post("/api/metrics/", response_model=MetricSchema)
async def create_metric(
    metric: MetricCreate,
    db: AsyncSession = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """
    Create a new metric entry.
    This endpoint allows adding a single metric to the system.
    The timestamp can be specified or will default to current UTC time.
    """
    db_metric = Metric.from_schema(metric)
    db.add(db_metric)
    await db.commit()
    await db.refresh(db_metric)
    return db_metric

@app.post("/api/metrics/bulk", response_model=List[MetricSchema])
async def create_metrics_bulk(
    metrics: MetricBulkCreate,
    db: AsyncSession = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """
    Bulk create multiple metric entries.
    This endpoint allows adding multiple metrics in a single request.
    Each metric can have its own timestamp or use the current UTC time as default.

    Example request body:
    {
        "metrics": [
            {
                "name": "cpu_usage",
                "value": 45.2,
                "unit": "%",
                "timestamp": "2025-02-19T12:30:00Z"
            },
            {
                "name": "memory_usage",
                "value": 1024.5,
                "unit": "MB"
            }
        ]
    }
    """
    db_metrics = [Metric.from_schema(m) for m in metrics.metrics]
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
    Renders the dashboard template with grouped metrics data and their history.
    """
    # Get all metrics grouped by name
    result = await db.execute(
        select(Metric.name).distinct()
    )
    metric_names = result.scalars().all()

    grouped_metrics = {}
    for name in metric_names:
        # Get historical data for each metric
        result = await db.execute(
            select(Metric)
            .filter(Metric.name == name)
            .order_by(Metric.timestamp.desc())
            .limit(20)  # Last 20 data points for the graph
        )
        metrics = result.scalars().all()
        if metrics:
            grouped_metrics[name] = {
                'current': metrics[0],  # Latest value
                'history': list(reversed(metrics))  # Historical data in chronological order
            }

    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "grouped_metrics": grouped_metrics}
    )

if __name__ == "__main__":
    uvicorn.run("web_app.main:app", host="0.0.0.0", port=8000, reload=True)
