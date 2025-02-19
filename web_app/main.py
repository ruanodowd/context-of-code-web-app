from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta
from typing import List
import uvicorn

from .database import get_db
from .models import Metric
from .schemas import MetricCreate, Metric as MetricSchema

app = FastAPI(
    title="Metrics Dashboard",
    description="A modern FastAPI dashboard for tracking various metrics",
    version="1.0.0"
)

# Mount static files directory
app.mount("/static", StaticFiles(directory="web_app/static"), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory="web_app/templates")

@app.post("/api/metrics/", response_model=MetricSchema)
async def create_metric(metric: MetricCreate, db: AsyncSession = Depends(get_db)):
    """
    Create a new metric entry.
    This endpoint allows adding new metrics to the system.
    """
    db_metric = Metric(
        name=metric.name,
        value=metric.value,
        unit=metric.unit
    )
    db.add(db_metric)
    await db.commit()
    await db.refresh(db_metric)
    return db_metric

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
