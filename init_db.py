import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from web_app.models import Base
from web_app.config import get_settings

settings = get_settings()

async def init_db():
    """Initialize the database by creating all tables."""
    print(f"Creating database tables using {settings.DATABASE_URL}")
    
    # Create async engine
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=True,
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    print("Database tables created successfully!")

if __name__ == "__main__":
    asyncio.run(init_db())
