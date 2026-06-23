"""
Analysis API endpoints for chart insight generation.

Provider selection is driven by settings.ANALYSIS_PROVIDER:
- "text"  (default): DeepSeek text model analyzes the chart spec + data summary.
- "vision": GLM-4.5v multimodal model analyzes the rendered thumbnail image
            (requires GLM_API_KEY and a generated thumbnail).
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
import logging
import os
import time

from ..core.database import get_db
from ..core.deps import require_api_key, get_llm_semaphore
from ..models.database import ChartSpec, Analysis, GenerationRun
from ..schemas.api import AnalysisRequest, AnalysisResponse, AnalysisNodePayload
from ..services.vision_provider import get_vision_provider
from ..services.text_analysis_provider import get_text_analysis_provider
from ..core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["analysis"])


async def _run_analysis(chart_spec: ChartSpec) -> tuple[str, str]:
    """
    Run analysis using the configured provider, gated by the global LLM
    concurrency semaphore (fix #3).

    Returns (analysis_text, model_tag).
    """
    provider = settings.ANALYSIS_PROVIDER.lower()

    async with get_llm_semaphore():
        if provider == "vision":
            # Need a thumbnail on disk for the vision model
            thumbnail_path = None
            if chart_spec.thumbnail_uri:
                thumbnail_filename = f"{chart_spec.id}.png"
                thumbnail_path = os.path.join(settings.THUMBNAILS_DIR, thumbnail_filename)
                if not os.path.exists(thumbnail_path):
                    thumbnail_path = None
            if not thumbnail_path:
                raise HTTPException(
                    status_code=400,
                    detail="Vision analysis requires a chart thumbnail. "
                           "Regenerate the chart, or switch ANALYSIS_PROVIDER=text.",
                )
            vision_provider = get_vision_provider()
            text = vision_provider.analyze_chart(
                image_path=thumbnail_path,
                spec=chart_spec.spec_json,
                prompt=chart_spec.prompt,
            )
            return text, settings.GLM_MODEL

        # Default: text-based DeepSeek analysis (no thumbnail required)
        text_provider = get_text_analysis_provider()
        text = await text_provider.analyze_chart(
            spec=chart_spec.spec_json,
            prompt=chart_spec.prompt,
        )
        return text, f"deepseek-text({settings.DEEPSEEK_MODEL})"


@router.post("", response_model=AnalysisResponse, dependencies=[Depends(require_api_key)])
async def analyze_chart(
    body: AnalysisRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Analyze a chart and return structured Markdown insights.

    Uses the provider configured by ANALYSIS_PROVIDER (default: DeepSeek text).
    """
    chart_spec_id = body.chart_spec_id

    chart_spec = db.query(ChartSpec).filter(ChartSpec.id == chart_spec_id).first()
    if not chart_spec:
        raise HTTPException(status_code=404, detail=f"Chart spec {chart_spec_id} not found")

    logger.info(f"Analyzing chart {chart_spec_id} (provider={settings.ANALYSIS_PROVIDER})")

    started = time.time()
    try:
        analysis_text, model_tag = await _run_analysis(chart_spec)
    except HTTPException:
        # Record failed run
        try:
            db.add(GenerationRun(
                kind="analysis",
                input={"chart_spec_id": chart_spec_id},
                output=None,
                status="failed",
                latency_ms=int((time.time() - started) * 1000),
            ))
            db.commit()
        except Exception:
            pass
        raise
    except Exception as e:
        logger.error(f"Analysis failed for chart {chart_spec_id}: {e}", exc_info=True)
        try:
            db.add(GenerationRun(
                kind="analysis",
                input={"chart_spec_id": chart_spec_id},
                output=None,
                status="failed",
                latency_ms=int((time.time() - started) * 1000),
            ))
            db.commit()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    analysis = Analysis(
        chart_spec_id=chart_spec_id,
        model_tag=model_tag,
        text=analysis_text,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    # Record successful analysis run for observability (fix #9)
    db.add(GenerationRun(
        kind="analysis",
        input={"chart_spec_id": chart_spec_id},
        output={"analysis_id": analysis.id, "chars": len(analysis_text)},
        status="success",
        latency_ms=int((time.time() - started) * 1000),
    ))
    db.commit()

    logger.info(f"Analysis saved: {analysis.id}, {len(analysis_text)} chars")

    node_payload = AnalysisNodePayload(
        type="analysis",
        id=analysis.id,
        data={
            "analysis_id": analysis.id,
            "chart_spec_id": chart_spec_id,
            "text": analysis_text,
            "model_tag": analysis.model_tag,
            "created_at": analysis.created_at.isoformat(),
        }
    )

    return AnalysisResponse(
        analysis_id=analysis.id,
        node_payload=node_payload,
    )


@router.put("/{analysis_id}", response_model=AnalysisNodePayload)
async def update_analysis(
    analysis_id: str,
    body: dict,
    db: Session = Depends(get_db),
):
    """Update (manually edit) the analysis text."""
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")

    new_text = body.get("text")
    if new_text is None:
        raise HTTPException(status_code=400, detail="Missing 'text' field")

    analysis.text = new_text
    db.commit()
    db.refresh(analysis)

    logger.info(f"Updated analysis {analysis_id}, new length: {len(new_text)} chars")

    node_payload = AnalysisNodePayload(
        type="analysis",
        id=analysis.id,
        data={
            "analysis_id": analysis.id,
            "chart_spec_id": analysis.chart_spec_id,
            "text": analysis.text,
            "model_tag": analysis.model_tag,
            "created_at": analysis.created_at.isoformat(),
        }
    )

    return node_payload


@router.get("/{analysis_id}", response_model=AnalysisNodePayload)
async def get_analysis(
    analysis_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve a previously saved analysis by id (fix for missing GET).

    Lets the frontend re-fetch the current DB record when reloading a workflow,
    instead of trusting a stale snapshot embedded in the saved workflow JSON.
    """
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")

    return AnalysisNodePayload(
        type="analysis",
        id=analysis.id,
        data={
            "analysis_id": analysis.id,
            "chart_spec_id": analysis.chart_spec_id,
            "text": analysis.text,
            "model_tag": analysis.model_tag,
            "created_at": analysis.created_at.isoformat(),
        }
    )
