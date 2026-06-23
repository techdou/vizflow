import os
import hashlib
from pathlib import Path
from src.core.config import settings

def compute_file_hash(file_bytes: bytes) -> str:
    """Compute SHA256 hash of file content"""
    return hashlib.sha256(file_bytes).hexdigest()

def save_dataset_file(file_bytes: bytes, filename: str) -> tuple[str, str]:
    """
    Save dataset file to storage.
    Returns (storage_uri, hash)
    """
    file_hash = compute_file_hash(file_bytes)
    
    # Use hash-based path to avoid collisions
    subdir = file_hash[:2]
    filepath = Path(settings.DATASETS_DIR) / subdir / f"{file_hash}_{filename}"
    
    os.makedirs(filepath.parent, exist_ok=True)
    
    with open(filepath, 'wb') as f:
        f.write(file_bytes)
    
    storage_uri = str(filepath)
    return storage_uri, file_hash

def save_thumbnail(chart_spec_id: str, image_bytes: bytes, ext: str = "png") -> str:
    """
    Save thumbnail image.
    Returns thumbnail_uri
    """
    filename = f"{chart_spec_id}.{ext}"
    filepath = Path(settings.THUMBNAILS_DIR) / filename
    
    with open(filepath, 'wb') as f:
        f.write(image_bytes)
    
    return str(filepath)
