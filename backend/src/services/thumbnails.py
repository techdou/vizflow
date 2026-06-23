"""
Thumbnail generation service using vl-convert.

vl-convert is an optional dependency: it downloads a large binary on install,
so this module degrades gracefully when it is not available. The frontend
renders charts via vega-embed regardless, and text-based analysis (the
default) does not require thumbnails.
"""

import io
import json
from src.core.logging import logger

try:
    import vl_convert as vlc
    _VLC_AVAILABLE = True
except Exception as _e:  # ImportError or download/init failures
    vlc = None
    _VLC_AVAILABLE = False
    logger.warning(f"vl-convert not available, thumbnail generation disabled ({_e}). "
                   "Frontend will still render charts via vega-embed.")

# Log when module is loaded
logger.info(f"thumbnails.py loaded (vl_convert={'available' if _VLC_AVAILABLE else 'disabled'})")


def is_thumbnail_available() -> bool:
    """Whether server-side thumbnail rendering is available."""
    return _VLC_AVAILABLE


def generate_thumbnail(spec: dict, chart_spec_id: str) -> bytes:
    """
    Generate PNG thumbnail from Vega-Lite spec using vl-convert.

    Args:
        spec: Vega-Lite JSON spec
        chart_spec_id: ID for logging

    Returns:
        PNG image bytes

    Raises:
        RuntimeError if vl-convert is not installed or rendering fails.
    """
    if not _VLC_AVAILABLE:
        raise RuntimeError(
            "vl-convert-python is not installed; server-side thumbnail "
            "generation is unavailable. The frontend renders charts via "
            "vega-embed instead."
        )

    try:
        logger.info(f"Generating thumbnail for chart_spec_id={chart_spec_id}")
        spec_json = json.dumps(spec)
        png_data = vlc.vegalite_to_png(vl_spec=spec_json, scale=2.0)
        logger.info(f"Generated thumbnail ({len(png_data)} bytes) for chart_spec_id={chart_spec_id}")
        return png_data
    except Exception as e:
        logger.error(f"Failed to generate thumbnail for chart_spec_id={chart_spec_id}: {e}", exc_info=True)
        raise

