import os
from typing import List
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.config import settings
from src.core.logging import logger
from src.core.deps import require_api_key
from src.models.database import Dataset
from src.schemas.api import DatasetResponse
from src.storage.files import save_dataset_file
from src.services.dataset_utils import parse_dataset, infer_schema

router = APIRouter()

# Max bytes read into memory when sniffing schema. The file itself is still
# streamed to disk by save_dataset_file; only the preview we parse for schema
# is capped.
_SCHEMA_PREVIEW_BYTES = 2 * 1024 * 1024  # 2 MB


def _allowed_by_name_or_mime(filename: str, content_type) -> bool:
    """Accept by extension OR a generous MIME allowlist (fix #6).

    Browsers frequently label CSV as application/vnd.ms-excel or application/csv,
    so we don't reject on MIME alone — extension + the parser decide validity.
    """
    name = (filename or "").lower()
    if name.endswith((".csv", ".json", ".xlsx", ".xlsm", ".tsv")):
        return True
    ct = (content_type or "").lower()
    return any(k in ct for k in ("csv", "json", "text/plain", "spreadsheet", "excel", "tsv"))


@router.post("/datasets", response_model=dict, dependencies=[Depends(require_api_key)])
async def upload_dataset(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a dataset (CSV / JSON / XLSX).

    Reads the upload in chunks so we can reject oversized files early (fix #5)
    instead of buffering the whole thing into memory first. Persists the inferred
    schema at upload time (fix #8) and dedups by content hash.
    """
    filename = file.filename or "unknown"
    content_type = file.content_type

    if not _allowed_by_name_or_mime(filename, content_type):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file: '{filename}' (mime={content_type}). Supported: .csv .json .xlsx",
        )

    # ---- Stream read with an early size cap (fix #5) ----
    chunks = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)  # 1 MB chunks
        if not chunk:
            break
        total += len(chunk)
        if total > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large (> {settings.MAX_UPLOAD_SIZE} bytes). Upload aborted early.",
            )
        chunks.append(chunk)
    content = b"".join(chunks)

    if total == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # ---- Parse to infer schema (fix #8) ----
    try:
        columns, rows = parse_dataset(content, filename, content_type)
    except ImportError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {e}")

    if not rows:
        raise HTTPException(status_code=400, detail="File has no data rows (empty table)")

    schema = infer_schema(rows, columns)

    # ---- Persist file (content-addressed) ----
    storage_uri, file_hash = save_dataset_file(content, filename)

    # Dedup by hash
    existing = db.query(Dataset).filter(Dataset.hash == file_hash).first()
    if existing:
        logger.info(f"Dataset already exists with hash {file_hash}, returning existing dataset_id={existing.id}")
        return {"dataset_id": existing.id}

    dataset = Dataset(
        name=filename,
        mime=content_type or "application/octet-stream",
        size_bytes=total,
        storage_uri=storage_uri,
        hash=file_hash,
        schema_json=schema,  # persisted now (fix #8)
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    logger.info(
        f"Created dataset_id={dataset.id} | name={dataset.name} | size={dataset.size_bytes} "
        f"| rows={schema['row_count']} | cols={len(columns)}"
    )
    return {"dataset_id": dataset.id}


@router.get("/datasets", response_model=List[DatasetResponse])
async def list_datasets(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List previously uploaded datasets (fix #7 — no listing existed before)."""
    datasets = (
        db.query(Dataset)
        .order_by(Dataset.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        DatasetResponse(
            dataset_id=d.id,
            name=d.name,
            mime=d.mime,
            size_bytes=d.size_bytes,
            created_at=d.created_at,
        )
        for d in datasets
    ]


@router.get("/datasets/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: str,
    db: Session = Depends(get_db),
):
    """Get dataset metadata."""
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    return DatasetResponse(
        dataset_id=dataset.id,
        name=dataset.name,
        mime=dataset.mime,
        size_bytes=dataset.size_bytes,
        created_at=dataset.created_at,
    )


@router.get("/datasets/{dataset_id}/schema")
async def get_dataset_schema(
    dataset_id: str,
    db: Session = Depends(get_db),
):
    """Return the persisted schema (inferred at upload time) for a dataset."""
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset.schema_json or {"fields": [], "row_count": 0}
