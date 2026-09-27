import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

# Assume TimescaleDB is accessible via a Postgres URI
DATABASE_URL = os.getenv("POSTGRES_URI", "postgresql+asyncpg://user:password@localhost:5432/timescaledb")

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)
Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# Helper placeholder for fetching Timescale timeseries data
async def get_node_timeseries(node_id: str, db: AsyncSession):
    # This would execute a standard AsyncSession query returning timeseries for the given node
    # e.g., result = await db.execute(select(NodeMetrics).where(NodeMetrics.node_id == node_id).order_by(NodeMetrics.time.desc()).limit(100))
    
    # Return placeholder data
    return [
        {"time": "2026-07-04T10:00:00Z", "metric": "inventory", "value": 1500},
        {"time": "2026-07-04T11:00:00Z", "metric": "inventory", "value": 1450},
    ]
