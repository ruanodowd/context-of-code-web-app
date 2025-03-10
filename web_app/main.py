from fastapi import FastAPI, Depends, HTTPException, Request, Security
from fastapi.security.api_key import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload
from typing import List
import uvicorn

from .database import get_db, init_db
from .models import Metric, MetricType, Unit, Source
from .schemas import (
    MetricCreate, MetricBulkCreate, Metric as MetricSchema,
    MetricType as MetricTypeSchema, MetricTypeCreate,
    Unit as UnitSchema, UnitCreate,
    Source as SourceSchema, SourceCreate
)
from .config import get_settings
from .command_relay import router as command_relay_router

settings = get_settings()

app = FastAPI(
    title="Metrics Dashboard",
    description="A modern FastAPI dashboard for tracking various metrics",
    version="1.0.0",
    debug=settings.DEBUG
)

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    await init_db()

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

# Include command relay router
app.include_router(command_relay_router)

# Setup Jinja2 templates with datetime filter
templates = Jinja2Templates(directory="web_app/templates")

# Add custom filters to Jinja2 environment
def format_datetime(value, format='%Y-%m-%d %H:%M:%S'):
    if value is None:
        return ''
    return value.strftime(format)

templates.env.filters['strftime'] = format_datetime

@app.get("/api/sources", response_model=List[SourceSchema])
@app.get("/api/sources/", response_model=List[SourceSchema])
async def list_sources(db: AsyncSession = Depends(get_db)):
    """List all available sources."""
    result = await db.execute(select(Source))
    return result.scalars().all()

@app.post("/api/sources", response_model=SourceSchema)
@app.post("/api/sources/", response_model=SourceSchema)
async def create_source(
    source: SourceCreate,
    db: AsyncSession = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """Create a new source."""
    # Check if source with same name exists
    result = await db.execute(
        select(Source).where(Source.name == source.name)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail=f"Source with name '{source.name}' already exists"
        )

    db_source = Source(**source.model_dump())
    db.add(db_source)
    await db.commit()
    await db.refresh(db_source)
    return db_source

@app.post("/api/units", response_model=UnitSchema)
async def create_unit(
    unit: UnitCreate,
    db: AsyncSession = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """Create a new unit definition."""
    # Check if unit with same name or symbol already exists
    result = await db.execute(
        select(Unit).where(
            or_(
                Unit.name == unit.name,
                Unit.symbol == unit.symbol
            )
        )
    )
    existing_unit = result.scalar_one_or_none()
    if existing_unit:
        if existing_unit.name == unit.name:
            detail = f"Unit with name '{unit.name}' already exists"
        else:
            detail = f"Unit with symbol '{unit.symbol}' already exists"
        raise HTTPException(status_code=400, detail=detail)

    db_unit = Unit(**unit.model_dump())
    db.add(db_unit)
    await db.commit()
    await db.refresh(db_unit)
    return db_unit

@app.get("/api/units", response_model=List[UnitSchema])
async def list_units(db: AsyncSession = Depends(get_db)):
    """List all available units."""
    result = await db.execute(select(Unit))
    return result.scalars().all()

# Helper function to serialize metric types
def serialize_metric_types(metric_types):
    """Convert metric types to JSON-serializable dictionaries"""
    return [
        {
            'id': str(mt.id),
            'name': mt.name,
            'description': mt.description,
            'unit': {
                'id': str(mt.unit.id),
                'name': mt.unit.name,
                'symbol': mt.unit.symbol,
                'description': mt.unit.description
            } if mt.unit else None,
            'created_at': mt.created_at.isoformat() if mt.created_at else None,
            'is_active': mt.is_active
        }
        for mt in metric_types
    ]

@app.post("/api/metric-types", response_model=MetricTypeSchema)
@app.post("/api/metric-types/", response_model=MetricTypeSchema)
async def create_metric_type(
    metric_type: MetricTypeCreate,
    db: AsyncSession = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """Create a new metric type definition."""
    # Verify unit exists
    result = await db.execute(
        select(Unit).where(Unit.id == metric_type.unit_id)
    )
    unit = result.scalar_one_or_none()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")

    db_metric_type = MetricType(**metric_type.model_dump())
    db.add(db_metric_type)
    await db.commit()
    await db.refresh(db_metric_type)
    return db_metric_type

@app.get("/api/metric-types", response_model=List[MetricTypeSchema])
@app.get("/api/metric-types/", response_model=List[MetricTypeSchema])
async def list_metric_types(db: AsyncSession = Depends(get_db)):
    """List all available metric types."""
    result = await db.execute(
        select(MetricType).options(selectinload(MetricType.unit))
    )
    return result.scalars().all()

@app.post("/api/metrics", response_model=MetricSchema)
async def create_metric(
    metric: MetricCreate,
    db: AsyncSession = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """Create a new metric measurement."""
    # If metric_type_name is provided, look up the metric type by name
    if metric.metric_type_name and not metric.metric_type_id:
        result = await db.execute(
            select(MetricType)
            .options(selectinload(MetricType.unit))
            .where(MetricType.name == metric.metric_type_name)
        )
        metric_type = result.scalar_one_or_none()
        if not metric_type:
            raise HTTPException(status_code=404, detail=f"Metric type '{metric.metric_type_name}' not found")
        metric.metric_type_id = metric_type.id
    else:
        # Verify metric type exists by ID
        result = await db.execute(
            select(MetricType)
            .options(selectinload(MetricType.unit))
            .where(MetricType.id == metric.metric_type_id)
        )
        metric_type = result.scalar_one_or_none()
        if not metric_type:
            raise HTTPException(status_code=404, detail="Metric type not found")

    # If source_name is provided, look up or create the source
    if metric.source_name and not metric.source_id:
        result = await db.execute(
            select(Source).where(Source.name == metric.source_name)
        )
        source = result.scalar_one_or_none()
        if not source:
            # Create new source
            source = Source(name=metric.source_name)
            db.add(source)
            await db.commit()
            await db.refresh(source)
        metric.source_id = source.id
    else:
        # Verify source exists by ID
        result = await db.execute(
            select(Source).where(Source.id == metric.source_id)
        )
        source = result.scalar_one_or_none()
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")

    # Create the metric
    metric_data = metric.model_dump(exclude={'metric_type_name', 'source_name'})
    db_metric = Metric(**metric_data)
    db.add(db_metric)
    await db.commit()
    
    # Refresh with all relationships loaded
    result = await db.execute(
        select(Metric)
        .options(
            selectinload(Metric.metric_type),
            selectinload(Metric.source),
            selectinload(Metric.metric_metadata_items)
        )
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

    # Verify all sources exist
    source_ids = {m.source_id for m in metrics.metrics}
    result = await db.execute(
        select(Source).where(Source.id.in_(source_ids))
    )
    found_sources = {s.id for s in result.scalars().all()}
    missing_sources = source_ids - found_sources
    if missing_sources:
        raise HTTPException(
            status_code=404,
            detail=f"Sources not found: {missing_sources}"
        )

    db_metrics = [Metric(**m.model_dump()) for m in metrics.metrics]
    db.add_all(db_metrics)
    await db.commit()
    
    # Get all metrics with relationships loaded
    metric_ids = [m.id for m in db_metrics]
    result = await db.execute(
        select(Metric)
        .options(
            selectinload(Metric.metric_type),
            selectinload(Metric.source),
            selectinload(Metric.metric_metadata_items)
        )
        .where(Metric.id.in_(metric_ids))
    )
    return result.scalars().all()

@app.get("/api/metrics", response_model=List[MetricSchema])
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
    # Get all metric types with their units
    result = await db.execute(
        select(MetricType)
        .options(selectinload(MetricType.unit))
        .order_by(MetricType.name)
    )
    metric_types = result.scalars().all()

    # Get historical data for each metric type
    metric_history = {}
    for metric_type in metric_types:
        result = await db.execute(
            select(Metric)
            .options(
                selectinload(Metric.metric_type),
                selectinload(Metric.source),
                selectinload(Metric.metric_metadata_items)
            )
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
                # Safely handle source and metadata
                source_data = {
                    'id': str(metric.source.id) if metric.source else None,
                    'name': metric.source.name if metric.source else None
                } if metric.source else None
                
                metadata_items = [{
                    'key': item.key,
                    'value': item.value
                } for item in metric.metric_metadata_items] if metric.metric_metadata_items else []
                
                metric_dict = {
                    'id': str(metric.id),  # Convert UUID to string
                    'value': metric.value,
                    'recorded_at': metric.recorded_at.isoformat() if metric.recorded_at else None,
                    'source': source_data,
                    'metric_metadata': metadata_items,
                    'metric_type_id': str(metric.metric_type_id)  # Convert UUID to string
                }
                serialized_metrics.append(metric_dict)
            metric_history[str(metric_type.id)] = serialized_metrics

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "metric_types": serialize_metric_types(metric_types),
            "metric_history": metric_history,
            "settings": settings
        }
    )

@app.get("/advanced")
async def advanced_dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Advanced dashboard view with speedometer gauge and filterable table.
    Renders the advanced_dashboard template with metric types and their history.
    """
    # Get all metric types with their units
    result = await db.execute(
        select(MetricType)
        .options(selectinload(MetricType.unit))
        .order_by(MetricType.name)
    )
    metric_types = result.scalars().all()

    # Get historical data for each metric type
    metric_history = {}
    for metric_type in metric_types:
        result = await db.execute(
            select(Metric)
            .options(
                selectinload(Metric.metric_type),
                selectinload(Metric.source),
                selectinload(Metric.metric_metadata_items)
            )
            .filter(Metric.metric_type_id == metric_type.id)
            .order_by(Metric.recorded_at.desc())
            .limit(100)  # Increased limit for the advanced dashboard
        )
        metrics = result.scalars().all()
        if metrics:
            # Convert metrics to a serializable format
            serialized_metrics = []
            for metric in metrics:
                # Safely handle source and metadata
                source_data = {
                    'id': str(metric.source.id) if metric.source else None,
                    'name': metric.source.name if metric.source else None
                } if metric.source else None
                
                metadata_items = [{
                    'key': item.key,
                    'value': item.value
                } for item in metric.metric_metadata_items] if metric.metric_metadata_items else []
                
                metric_dict = {
                    'id': str(metric.id),  # Convert UUID to string
                    'value': metric.value,
                    'recorded_at': metric.recorded_at.isoformat() if metric.recorded_at else None,
                    'source': source_data,
                    'metric_metadata': metadata_items,
                    'metric_type_id': str(metric.metric_type_id)  # Convert UUID to string
                }
                serialized_metrics.append(metric_dict)
            metric_history[str(metric_type.id)] = serialized_metrics

    return templates.TemplateResponse(
        "advanced_dashboard.html",
        {
            "request": request,
            "metric_types": serialize_metric_types(metric_types),
            "metric_history": metric_history,
            "settings": settings
        }
    )

# Current dashboard route
@app.get("/current")
async def current_dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Current dashboard view with time-relative line graphs and command controls.
    Renders the current_dashboard template with metric types and their history.
    """
    # Get all metric types with their units
    result = await db.execute(
        select(MetricType)
        .options(selectinload(MetricType.unit))
        .order_by(MetricType.name)
    )
    metric_types = result.scalars().all()

    # Get historical data for each metric type
    metric_history = {}
    for metric_type in metric_types:
        result = await db.execute(
            select(Metric)
            .options(
                selectinload(Metric.metric_type),
                selectinload(Metric.source),
                selectinload(Metric.metric_metadata_items)
            )
            .filter(Metric.metric_type_id == metric_type.id)
            .order_by(Metric.recorded_at.desc())
            .limit(100)  # Only get the last 100 metrics for performance
        )
        metrics = result.scalars().all()
        if metrics:
            # Convert metrics to a serializable format
            serialized_metrics = []
            for metric in metrics:
                # Safely handle source and metadata
                source_data = {
                    'id': str(metric.source.id) if metric.source else None,
                    'name': metric.source.name if metric.source else None
                } if metric.source else None
                
                metadata_items = [{
                    'key': item.key,
                    'value': item.value
                } for item in metric.metric_metadata_items] if metric.metric_metadata_items else []
                
                metric_dict = {
                    'id': str(metric.id),
                    'value': metric.value,
                    'recorded_at': metric.recorded_at.isoformat() if metric.recorded_at else None,
                    'source': source_data,
                    'metric_metadata': metadata_items,
                    'metric_type_id': str(metric.metric_type_id)
                }
                serialized_metrics.append(metric_dict)
            metric_history[str(metric_type.id)] = serialized_metrics

    return templates.TemplateResponse(
        "current_dashboard.html",
        {
            "request": request,
            "metric_types": serialize_metric_types(metric_types),
            "metric_history": metric_history,
            "settings": settings
        }
    )

# Command relay dashboard route
@app.get("/command-relay")
async def command_relay_dashboard(request: Request):
    """
    Command relay dashboard view.
    Renders the command relay dashboard template.
    """
    return templates.TemplateResponse(
        "command_relay.html",
        {
            "request": request,
            "settings": settings
        }
    )

if __name__ == "__main__":
    uvicorn.run("web_app.main:app", host="0.0.0.0", port=8000, reload=True)
