from typing import Optional, Any
from pydantic import BaseModel
from datetime import datetime

# Dataset schemas
class DatasetCreate(BaseModel):
    name: str
    mime: str
    size_bytes: int

class DatasetResponse(BaseModel):
    dataset_id: str
    name: str
    mime: str
    size_bytes: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Chart schemas
class ChartGenerateRequest(BaseModel):
    dataset_id: str
    prompt: Optional[str] = None
    policy_id: Optional[str] = None
    spec_json: Optional[dict] = None  # For manual spec updates

class ChartNodePayload(BaseModel):
    type: str = "chart"  # Node type for React Flow
    id: str  # chart_spec_id used as node id
    data: dict  # Node data containing chart info
    
    @classmethod
    def from_chart_spec(cls, chart_spec_id: str, dataset_id: str, spec_json: Any, 
                       thumbnail_uri: Optional[str] = None, prompt: Optional[str] = None):
        """Factory method to create ChartNodePayload from chart spec"""
        return cls(
            type="chart",
            id=chart_spec_id,
            data={
                "chart_spec_id": chart_spec_id,
                "dataset_id": dataset_id,
                "vega_lite_spec": spec_json,
                "thumbnail_uri": thumbnail_uri,
                "prompt": prompt
            }
        )

class ChartGenerateResponse(BaseModel):
    chart_spec_id: str
    node_payload: ChartNodePayload

# Analysis schemas
class AnalysisRequest(BaseModel):
    chart_spec_id: str

class AnalysisNodePayload(BaseModel):
    type: str  # "analysis"
    id: str
    data: dict[str, Any]

class AnalysisResponse(BaseModel):
    analysis_id: str
    node_payload: AnalysisNodePayload

# Workflow schemas
class WorkflowElements(BaseModel):
    elements: Any  # React Flow elements structure

class WorkflowResponse(BaseModel):
    id: str
    name: str
    elements: Any
    created_at: datetime
    updated_at: datetime
