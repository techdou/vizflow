"""
Workflows API endpoints for saving and loading React Flow canvas state.
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Any
import logging

from ..core.database import get_db
from ..models.database import Workflow
from ..schemas.api import WorkflowElements, WorkflowResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("/{id}", response_model=WorkflowResponse)
async def get_workflow(id: str, db: Session = Depends(get_db)):
    """
    Get workflow by ID.
    Returns React Flow elements and metadata.
    """
    workflow = db.query(Workflow).filter(Workflow.id == id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow {id} not found")
    
    logger.info(f"Retrieved workflow {id}")
    return WorkflowResponse(
        id=workflow.id,
        name=workflow.name,
        elements=workflow.elements_json,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
    )


@router.put("/{id}")
async def save_workflow(
    id: str,
    body: WorkflowElements,
    db: Session = Depends(get_db),
):
    """
    Save or update workflow elements.
    Creates new workflow if ID doesn't exist, updates if it does.
    """
    workflow = db.query(Workflow).filter(Workflow.id == id).first()
    
    if workflow:
        # Update existing
        workflow.elements_json = body.elements
        logger.info(f"Updated workflow {id}")
    else:
        # Create new
        workflow = Workflow(
            id=id,
            name=f"Workflow {id[:8]}",
            elements_json=body.elements,
        )
        db.add(workflow)
        logger.info(f"Created new workflow {id}")
    
    db.commit()
    db.refresh(workflow)
    
    return {
        "id": workflow.id,
        "name": workflow.name,
        "updated_at": workflow.updated_at,
    }


@router.post("/export/{id}")
async def export_workflow(id: str, db: Session = Depends(get_db)):
    """
    Export workflow as JSON for download.
    Returns complete workflow data including metadata.
    """
    workflow = db.query(Workflow).filter(Workflow.id == id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow {id} not found")
    
    export_data = {
        "version": "elements_v1",
        "workflow": {
            "id": workflow.id,
            "name": workflow.name,
            "created_at": workflow.created_at.isoformat(),
            "updated_at": workflow.updated_at.isoformat(),
        },
        "elements": workflow.elements_json,
        "layout_meta": workflow.layout_meta,
    }
    
    logger.info(f"Exported workflow {id}")
    return export_data


@router.post("/import")
async def import_workflow(data: dict[str, Any], db: Session = Depends(get_db)):
    """
    Import workflow from exported JSON.
    Creates new workflow with imported data.
    """
    # Validate version
    version = data.get("version")
    if version != "elements_v1":
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported workflow version: {version}",
        )
    
    # Extract data
    workflow_meta = data.get("workflow", {})
    elements = data.get("elements")
    layout_meta = data.get("layout_meta")
    
    if not elements:
        raise HTTPException(status_code=400, detail="Missing elements in import data")
    
    # Create new workflow
    workflow = Workflow(
        name=workflow_meta.get("name", "Imported Workflow"),
        elements_json=elements,
        layout_meta=layout_meta,
    )
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    
    logger.info(f"Imported workflow as new ID {workflow.id}")
    return {
        "id": workflow.id,
        "name": workflow.name,
        "created_at": workflow.created_at,
    }
