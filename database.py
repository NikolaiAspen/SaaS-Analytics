from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from models.subscription import Base
from config import settings
# Import all models to register them with Base.metadata
from models import User, AppVersion, EmailLog
# Force reload for churned_customers column


# Fix DATABASE_URL if it's missing +asyncpg (Railway compatibility)
database_url = settings.database_url
if database_url.startswith("postgresql://") and "+asyncpg" not in database_url:
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
    print(f"[INFO] Fixed DATABASE_URL to use asyncpg driver: {database_url[:50]}...")

# Create async engine
engine = create_async_engine(
    database_url,
    echo=settings.app_env == "dev",
    poolclass=NullPool if "sqlite" in settings.database_url else None,
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """Dependency for getting database sessions"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
