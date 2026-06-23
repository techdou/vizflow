"""
Test thumbnail generation with vl-convert.
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from services.thumbnails import generate_thumbnail
from storage.files import save_thumbnail
from core.config import settings


def test_thumbnail_generation():
    """Test that thumbnails are generated correctly"""
    
    # Simple bar chart spec
    spec = {
        "mark": "bar",
        "data": {
            "values": [
                {"category": "A", "value": 28},
                {"category": "B", "value": 55},
                {"category": "C", "value": 43}
            ]
        },
        "encoding": {
            "x": {"field": "category", "type": "nominal"},
            "y": {"field": "value", "type": "quantitative"}
        }
    }
    
    chart_id = "test-thumbnail-001"
    
    print("\nStep 1: Generate thumbnail from spec...")
    thumbnail_bytes = generate_thumbnail(spec, chart_id)
    
    assert thumbnail_bytes, "Thumbnail bytes should not be empty"
    assert len(thumbnail_bytes) > 1000, f"Thumbnail too small: {len(thumbnail_bytes)} bytes"
    
    # Check that it's a valid PNG
    assert thumbnail_bytes.startswith(b'\x89PNG'), "Should be valid PNG format"
    
    print(f"✓ Generated {len(thumbnail_bytes)} bytes")
    
    print("\nStep 2: Save thumbnail to disk...")
    save_thumbnail(chart_id, thumbnail_bytes, "png")
    
    # Verify file exists
    thumbnail_path = os.path.join(settings.THUMBNAILS_DIR, f"{chart_id}.png")
    assert os.path.exists(thumbnail_path), f"Thumbnail file not found at {thumbnail_path}"
    
    file_size = os.path.getsize(thumbnail_path)
    assert file_size == len(thumbnail_bytes), "File size mismatch"
    
    print(f"✓ Saved to {thumbnail_path}")
    print(f"✓ File size: {file_size} bytes")
    
    print("\n✅ Thumbnail generation test PASSED!")
    
    # Cleanup
    if os.path.exists(thumbnail_path):
        os.remove(thumbnail_path)
        print(f"✓ Cleaned up test file")


if __name__ == "__main__":
    test_thumbnail_generation()
