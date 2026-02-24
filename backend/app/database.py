"""Database connection and models for TerraWatch."""

from __future__ import annotations

import datetime
from typing import AsyncGenerator, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    JSON,
    Boolean,
    Index,
    event,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class SoilAnalysisRecord(Base):
    """Stores soil analysis results for queried locations."""

    __tablename__ = "soil_analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)
    elevation_m = Column(Float)
    country = Column(String(100))
    region = Column(String(200))

    # Soil properties
    ph = Column(Float)
    ph_confidence = Column(Float)
    organic_carbon_pct = Column(Float)
    nitrogen_pct = Column(Float)
    moisture_pct = Column(Float)
    sand_pct = Column(Float)
    silt_pct = Column(Float)
    clay_pct = Column(Float)
    texture_class = Column(String(50))
    bulk_density = Column(Float)
    cec = Column(Float)

    # Health index
    health_score = Column(Float)
    health_grade = Column(String(10))

    # Erosion
    rusle_value = Column(Float)
    erosion_risk_level = Column(String(20))
    erosion_factors = Column(JSON)

    # Carbon
    carbon_stock = Column(Float)
    carbon_potential = Column(Float)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (
        Index("idx_soil_lat_lon", "latitude", "longitude"),
    )


class DisasterRiskRecord(Base):
    """Stores disaster risk assessments."""

    __tablename__ = "disaster_risks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)

    # Risk scores
    landslide_probability = Column(Float)
    landslide_risk_level = Column(String(20))
    flood_probability = Column(Float)
    flood_risk_level = Column(String(20))
    liquefaction_susceptibility = Column(String(20))
    wildfire_probability = Column(Float)
    wildfire_risk_level = Column(String(20))

    composite_risk_score = Column(Float)
    composite_risk_level = Column(String(30))

    details = Column(JSON)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (
        Index("idx_risk_lat_lon", "latitude", "longitude"),
    )


class EarthquakeEvent(Base):
    """Real-time earthquake events from USGS."""

    __tablename__ = "earthquake_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(50), unique=True, nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    depth_km = Column(Float)
    magnitude = Column(Float)
    magnitude_type = Column(String(10))
    place = Column(String(300))
    event_time = Column(DateTime)
    url = Column(String(500))
    felt = Column(Integer)
    tsunami = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Alert(Base):
    """System alerts for risk events."""

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_type = Column(String(30), nullable=False)  # earthquake, landslide, flood, fire
    severity = Column(String(20), nullable=False)  # critical, warning, watch, advisory
    title = Column(String(300), nullable=False)
    description = Column(Text)
    latitude = Column(Float)
    longitude = Column(Float)
    radius_km = Column(Float)
    data = Column(JSON)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime)


async def init_db() -> None:
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
