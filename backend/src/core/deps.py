"""
Shared FastAPI dependencies: API-key auth + global LLM concurrency limit (fix #3).

Auth model:
    - If settings.VIZFLOW_API_KEY is set, every request to a protected route must
      include header `X-API-Key: <key>` matching it. Mismatch/missing → 401.
    - If unset, auth is disabled (local dev). A startup warning is logged.

Concurrency model:
    - A single asyncio.Semaphore(MAX_CONCURRENT_LLM) gates chart-generation and
      analysis calls so a burst of clients can't exhaust the DeepSeek quota.
"""
import asyncio
from typing import Optional

from fastapi import Header, HTTPException, status

from src.core.config import settings
from src.core.logging import logger

# Global semaphore, sized from config. Lazily created on first use so it binds
# to the running event loop regardless of import order.
_llm_semaphore: Optional[asyncio.Semaphore] = None


def get_llm_semaphore() -> asyncio.Semaphore:
    global _llm_semaphore
    if _llm_semaphore is None:
        _llm_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_LLM)
        logger.info(f"LLM concurrency semaphore initialized (max={settings.MAX_CONCURRENT_LLM})")
    return _llm_semaphore


async def require_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    """Dependency: enforce X-API-Key header when VIZFLOW_API_KEY is configured."""
    expected = settings.VIZFLOW_API_KEY
    if not expected:
        # Auth disabled (local dev). Nothing to check.
        return None
    if not x_api_key or x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid X-API-Key header",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return x_api_key
