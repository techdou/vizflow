import hashlib
import json
import csv
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path

from src.core.database import get_db, SessionLocal
from src.core.config import settings
from src.core.logging import logger
from src.core.deps import require_api_key, get_llm_semaphore
from src.models.database import Dataset, ChartSpec, GenerationRun
from src.schemas.api import ChartGenerateRequest, ChartGenerateResponse, ChartNodePayload
from src.services.llm_provider import generate_chart_spec, validate_vega_lite_spec
from src.services.thumbnails import generate_thumbnail
from src.storage.files import save_thumbnail

router = APIRouter()

def compute_cache_key(dataset_id: str, prompt: str, policy: str, model: str, dataset_hash: str = "") -> str:
    """
    Compute cache key for chart generation.

    Includes the dataset content hash so that changing the underlying data
    invalidates the cache (fix #2a). Policy version should be incremented
    when prompt logic changes to invalidate old cached results.
    """
    key_str = f"{dataset_id}|{dataset_hash}|{prompt}|{policy}|{model}"
    return hashlib.sha256(key_str.encode()).hexdigest()


def get_dataset_preview(dataset: Dataset, max_rows: int = None) -> dict:
    """
    Read dataset file and return preview with schema info.
    
    Args:
        dataset: Dataset model instance
        max_rows: Maximum number of rows to include (None = all rows, respects MAX_ROWS limit)
    
    Returns:
        Dictionary with columns, sample_data, total_rows, filename
    """
    # storage_uri is already a full path, don't concatenate DATASETS_DIR again
    filepath = Path(dataset.storage_uri)
    
    if not filepath.exists():
        logger.warning(f"Dataset file not found: {filepath}")
        return {"error": "Dataset file not found"}
    
    try:
        # Determine row limit
        if max_rows is None:
            max_rows = settings.MAX_ROWS  # Use global limit from config
        
        # Read CSV
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = []
            total_count = 0
            
            for i, row in enumerate(reader):
                total_count += 1
                if i < max_rows:
                    rows.append(row)
                elif i >= max_rows:
                    # Continue counting but don't store more rows
                    continue
        
        columns = list(rows[0].keys()) if rows else []
        
        return {
            "columns": columns,
            "sample_data": rows,  # All rows up to max_rows
            "total_rows": total_count,  # Total count in file
            "filename": dataset.name,
            "mime_type": dataset.mime
        }
    except Exception as e:
        logger.error(f"Failed to read dataset preview: {e}")
        return {"error": str(e)}

async def generate_thumbnail_background(chart_spec_id: str, spec: dict, db_url: str):
    """Background task to generate thumbnail and update database.

    Silently skips when vl-convert is unavailable (frontend renders via vega-embed).
    Reuses the global SessionLocal instead of creating a new engine (fix #4)."""
    try:
        from src.services.thumbnails import is_thumbnail_available
        if not is_thumbnail_available():
            logger.info(f"Skipping thumbnail for chart_spec_id={chart_spec_id} (vl-convert unavailable)")
            return

        # Generate and save thumbnail
        thumbnail_bytes = generate_thumbnail(spec, chart_spec_id)
        if thumbnail_bytes:
            save_thumbnail(chart_spec_id, thumbnail_bytes, "png")
            logger.info(f"Thumbnail saved for chart_spec_id={chart_spec_id}")

            # Update database with thumbnail_uri using the shared session factory.
            db = SessionLocal()
            try:
                chart_spec = db.query(ChartSpec).filter(ChartSpec.id == chart_spec_id).first()
                if chart_spec:
                    chart_spec.thumbnail_uri = f"/api/thumbnails/{chart_spec_id}.png"
                    db.commit()
                    logger.info(f"Updated thumbnail_uri for chart_spec_id={chart_spec_id}")
            finally:
                db.close()

    except Exception as e:
        logger.error(f"Background thumbnail generation failed for chart_spec_id={chart_spec_id}: {e}")

@router.post("/charts", response_model=ChartGenerateResponse, dependencies=[Depends(require_api_key)])
async def generate_chart(
    request: ChartGenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Generate chart spec from dataset and prompt"""
    
    # Verify dataset exists
    dataset = db.query(Dataset).filter(Dataset.id == request.dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Compute cache key — includes dataset content hash (fix #2a)
    prompt = request.prompt or "auto"
    policy_version = "v2-6step"  # Updated: v2 with 6-step reasoning prompt
    model_tag = settings.DEEPSEEK_MODEL
    cache_key = compute_cache_key(request.dataset_id, prompt, policy_version, model_tag, dataset.hash)
    
    # Check cache
    existing = db.query(ChartSpec).filter(ChartSpec.cache_key == cache_key).first()
    if existing:
        logger.info(f"Cache hit for cache_key={cache_key}, returning chart_spec_id={existing.id}")
        
        node_payload = ChartNodePayload.from_chart_spec(
            chart_spec_id=existing.id,
            dataset_id=existing.dataset_id,
            spec_json=existing.spec_json,
            thumbnail_uri=f"/api/thumbnails/{existing.id}.png" if existing.thumbnail_uri else None,
            prompt=existing.prompt
        )
        
        return ChartGenerateResponse(
            chart_spec_id=existing.id,
            node_payload=node_payload
        )
    
    # Generate new spec
    import time
    started = time.time()
    run_status = "success"
    run_error = None
    try:
        # Get dataset preview for LLM (read all data up to MAX_ROWS limit)
        dataset_preview = get_dataset_preview(dataset, max_rows=None)
        
        # Log preview for debugging
        if "error" in dataset_preview:
            logger.error(f"Failed to read dataset preview: {dataset_preview['error']}")
            raise HTTPException(status_code=400, detail=f"Cannot read dataset: {dataset_preview['error']}")
        
        total_rows = dataset_preview.get('total_rows', len(dataset_preview.get('sample_data', [])))
        data_rows = len(dataset_preview.get('sample_data', []))
        logger.info(
            f"Dataset loaded: {data_rows} rows (total: {total_rows}), "
            f"columns={dataset_preview.get('columns', [])}"
        )
        
        # Gate the LLM call behind the global concurrency limit (fix #3)
        async with get_llm_semaphore():
            spec = await generate_chart_spec(
                dataset_id=request.dataset_id,
                prompt=request.prompt,
                dataset_preview=dataset_preview
            )
        
        # Validate spec
        is_valid, error = validate_vega_lite_spec(spec)
        if not is_valid:
            run_status, run_error = "failed", f"Invalid spec: {error}"
            raise HTTPException(status_code=400, detail=f"Invalid spec: {error}")
        
        # Save chart spec
        chart_spec = ChartSpec(
            dataset_id=request.dataset_id,
            prompt=request.prompt,
            spec_json=spec,
            policy_version=policy_version,
            model_tag=model_tag,
            validation_report={"valid": True},
            thumbnail_uri=None,  # Will be set by background task
            cache_key=cache_key
        )
        
        db.add(chart_spec)
        db.commit()
        db.refresh(chart_spec)
        
        logger.info(f"Created chart_spec_id={chart_spec.id} for dataset_id={request.dataset_id}")
        
        # Record this generation run for observability (fix #9)
        db.add(GenerationRun(
            kind="chart",
            input={"dataset_id": request.dataset_id, "prompt": request.prompt},
            output={"chart_spec_id": chart_spec.id, "mark": spec.get("mark")},
            status=run_status,
            latency_ms=int((time.time() - started) * 1000),
        ))
        db.commit()
        
        # Schedule thumbnail generation in background
        background_tasks.add_task(generate_thumbnail_background, chart_spec.id, spec, settings.DB_URL)
        
        node_payload = ChartNodePayload.from_chart_spec(
            chart_spec_id=chart_spec.id,
            dataset_id=chart_spec.dataset_id,
            spec_json=chart_spec.spec_json,
            thumbnail_uri=f"/api/thumbnails/{chart_spec.id}.png",
            prompt=chart_spec.prompt
        )
        
        return ChartGenerateResponse(
            chart_spec_id=chart_spec.id,
            node_payload=node_payload
        )
        
    except HTTPException:
        # Record the failure before re-raising
        try:
            db.add(GenerationRun(
                kind="chart",
                input={"dataset_id": request.dataset_id, "prompt": request.prompt},
                output=None,
                status="failed",
                latency_ms=int((time.time() - started) * 1000),
            ))
            db.commit()
        except Exception:
            pass
        raise
    except Exception as e:
        logger.error(f"Chart generation failed: {e}", exc_info=True)
        try:
            db.add(GenerationRun(
                kind="chart",
                input={"dataset_id": request.dataset_id, "prompt": request.prompt},
                output=None,
                status="failed",
                latency_ms=int((time.time() - started) * 1000),
            ))
            db.commit()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Chart generation failed: {str(e)}")

@router.get("/thumbnails/{chart_spec_id}.png")
async def get_thumbnail(chart_spec_id: str, db: Session = Depends(get_db)):
    """Get chart thumbnail image"""
    
    filepath = Path(settings.THUMBNAILS_DIR) / f"{chart_spec_id}.png"
    
    if not filepath.exists():
        # Return placeholder or 404
        raise HTTPException(status_code=404, detail="Thumbnail not available")
    
    return FileResponse(filepath, media_type="image/png")


@router.put("/charts/{chart_spec_id}", response_model=ChartGenerateResponse, dependencies=[Depends(require_api_key)])
async def update_chart(
    chart_spec_id: str,
    request: ChartGenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Update existing chart with new spec (manual edit) or regenerate with new prompt.
    Creates a new ChartSpec entry to preserve version history.
    """
    
    # Verify original chart exists
    original_chart = db.query(ChartSpec).filter(ChartSpec.id == chart_spec_id).first()
    if not original_chart:
        raise HTTPException(status_code=404, detail="Chart spec not found")
    
    # Verify dataset exists
    dataset = db.query(Dataset).filter(Dataset.id == request.dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Determine if this is a manual edit or regeneration
    if hasattr(request, 'spec_json') and request.spec_json:
        # Manual edit: use provided spec
        spec = request.spec_json
        logger.info(f"Updating chart_spec_id={chart_spec_id} with manual edit")
    else:
        # Regeneration: call LLM with new prompt
        logger.info(f"Regenerating chart_spec_id={chart_spec_id} with new prompt")
        
        dataset_preview = get_dataset_preview(dataset, max_rows=None)
        
        if "error" in dataset_preview:
            raise HTTPException(status_code=400, detail=f"Cannot read dataset: {dataset_preview['error']}")
        
        # Gate regeneration behind the global concurrency limit (fix #3)
        async with get_llm_semaphore():
            spec = await generate_chart_spec(
                dataset_id=request.dataset_id,
                prompt=request.prompt,
                dataset_preview=dataset_preview
            )
    
    # Validate spec
    is_valid, error = validate_vega_lite_spec(spec)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid spec: {error}")
    
    # Create new ChartSpec (versioning)
    prompt = request.prompt or original_chart.prompt
    policy_version = "v2-6step"
    model_tag = settings.DEEPSEEK_MODEL
    # Re-derived chart uses the dataset hash; add a "v2" suffix so the updated
    # row never collides with the original's cache_key (fix #2b). cache_key is
    # no longer unique-constrained, but distinct keys keep the lookup path clean.
    ds = db.query(Dataset).filter(Dataset.id == request.dataset_id).first()
    ds_hash = ds.hash if ds else ""
    cache_key = compute_cache_key(request.dataset_id, prompt, policy_version, model_tag, ds_hash) + ":upd"
    
    new_chart_spec = ChartSpec(
        dataset_id=request.dataset_id,
        prompt=prompt,
        spec_json=spec,
        policy_version=policy_version,
        model_tag=model_tag,
        validation_report={"valid": True, "updated_from": chart_spec_id},
        thumbnail_uri=None,
        cache_key=cache_key
    )
    
    db.add(new_chart_spec)
    db.commit()
    db.refresh(new_chart_spec)
    
    logger.info(f"Created updated chart_spec_id={new_chart_spec.id} (previous: {chart_spec_id})")
    
    # Schedule thumbnail generation
    background_tasks.add_task(generate_thumbnail_background, new_chart_spec.id, spec, settings.DB_URL)
    
    node_payload = ChartNodePayload.from_chart_spec(
        chart_spec_id=new_chart_spec.id,
        dataset_id=new_chart_spec.dataset_id,
        spec_json=new_chart_spec.spec_json,
        thumbnail_uri=f"/api/thumbnails/{new_chart_spec.id}.png",
        prompt=new_chart_spec.prompt
    )
    
    return ChartGenerateResponse(
        chart_spec_id=new_chart_spec.id,
        node_payload=node_payload
    )
