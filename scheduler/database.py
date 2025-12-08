from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost/scheduler")

engine = create_async_engine(DATABASE_URL, echo=True)

SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

async def get_db_session():
    async with SessionLocal() as session:
        yield session

# Etcd Setup
import etcd3
ETCD_HOST = os.getenv("ETCD_HOST", "localhost")
ETCD_PORT = int(os.getenv("ETCD_PORT", 2379))

def get_etcd_client():
    return etcd3.client(host=ETCD_HOST, port=ETCD_PORT)
