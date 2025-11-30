import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in .env")

engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    future=True,
)
async_session_maker = sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


async def get_session():
    async with AsyncSessionLocal() as session:
        yield session