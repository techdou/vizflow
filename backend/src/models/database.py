import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, JSON, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from src.core.database import Base

def gen_uuid():
    return str(uuid.uuid4())

class Dataset(Base):
    __tablename__ = "datasets"
    
    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    mime = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    schema_json = Column(JSON, nullable=True)
    storage_uri = Column(String, nullable=False)
    hash = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ChartSpec(Base):
    __tablename__ = "chart_specs"
    
    id = Column(String, primary_key=True, default=gen_uuid)
    dataset_id = Column(String, ForeignKey("datasets.id"), nullable=False, index=True)
    prompt = Column(Text, nullable=True)
    spec_json = Column(JSON, nullable=False)
    policy_version = Column(String, nullable=False)
    model_tag = Column(String, nullable=False)
    validation_report = Column(JSON, nullable=True)
    thumbnail_uri = Column(String, nullable=True)
    # NOTE: cache_key is indexed but NOT unique — regenerate / update paths may
    # legitimately produce a second row with the same logical key (e.g. a user
    # regenerates with the same prompt). The generate endpoint checks for an
    # existing hit BEFORE inserting, which is sufficient for caching semantics;
    # a DB-level unique constraint would crash those write paths (fix #2b).
    cache_key = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class Analysis(Base):
    __tablename__ = "analyses"
    
    id = Column(String, primary_key=True, default=gen_uuid)
    chart_spec_id = Column(String, ForeignKey("chart_specs.id"), nullable=False, index=True)
    model_tag = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    tags = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class Workflow(Base):
    __tablename__ = "workflows"
    
    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False, default="Untitled Workflow")
    elements_json = Column(JSON, nullable=False)
    layout_meta = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class GenerationRun(Base):
    __tablename__ = "generation_runs"
    
    id = Column(String, primary_key=True, default=gen_uuid)
    kind = Column(String, nullable=False)  # "chart" or "analysis"
    input = Column(JSON, nullable=False)
    output = Column(JSON, nullable=True)
    status = Column(String, nullable=False)  # "success", "failed", "timeout"
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
