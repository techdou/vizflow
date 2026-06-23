"""
GLM-4.5v Vision Provider for multimodal chart analysis.

This service integrates with Zhipu AI's GLM-4.5v model to analyze chart visualizations
by processing both image (Base64 encoded thumbnail) and structured text (spec metadata).
"""
import base64
import logging
from typing import Optional, Any
from openai import OpenAI

from ..core.config import settings

logger = logging.getLogger(__name__)


class GLMVisionProvider:
    """
    GLM-4.5v multimodal vision provider for chart analysis.
    
    Uses OpenAI-compatible API with GLM-4.5v model for analyzing
    chart thumbnails combined with spec metadata.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 2,
    ):
        """
        Initialize GLM vision provider.
        
        Args:
            api_key: GLM API key (defaults to settings.GLM_API_KEY)
            base_url: GLM API base URL (defaults to settings.GLM_BASE_URL)
            model: Model name (defaults to settings.GLM_MODEL)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries
        """
        self.api_key = api_key or settings.GLM_API_KEY
        if not self.api_key:
            raise ValueError("GLM_API_KEY not set in environment or config")
        
        self.model = model or settings.GLM_MODEL
        self.base_url = base_url or settings.GLM_BASE_URL
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=timeout,
            max_retries=max_retries,
        )
        
        logger.info(f"Initialized GLM Vision Provider with model={self.model}")
    
    def _encode_image_file(self, image_path: str) -> str:
        """
        Encode image file to Base64 string.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Base64 encoded image with data URI prefix
        """
        with open(image_path, "rb") as f:
            image_data = f.read()
        
        # Encode to base64
        base64_image = base64.b64encode(image_data).decode("utf-8")
        
        # Determine MIME type
        if image_path.lower().endswith(".png"):
            mime_type = "image/png"
        elif image_path.lower().endswith((".jpg", ".jpeg")):
            mime_type = "image/jpeg"
        else:
            mime_type = "image/png"  # Default
        
        return f"data:{mime_type};base64,{base64_image}"
    
    def _sanitize_spec(self, spec: dict[str, Any]) -> dict[str, Any]:
        """
        Remove large data arrays from spec to reduce payload size.
        
        Keeps spec structure (mark, encoding, transform) but removes data.values.
        
        Args:
            spec: Full Vega-Lite spec
            
        Returns:
            Sanitized spec with data summary
        """
        sanitized = spec.copy()
        
        # Remove large data values array
        if "data" in sanitized and "values" in sanitized.get("data", {}):
            data_values = sanitized["data"]["values"]
            row_count = len(data_values) if isinstance(data_values, list) else 0
            
            # Replace with summary
            sanitized["data"] = {
                "_summary": f"{row_count} rows",
                "_fields": list(data_values[0].keys()) if row_count > 0 and isinstance(data_values[0], dict) else []
            }
        
        return sanitized
    
    def analyze_chart(
        self,
        image_path: str,
        spec: dict[str, Any],
        prompt: Optional[str] = None,
        custom_instruction: Optional[str] = None,
    ) -> str:
        """
        Analyze chart using GLM-4.5v multimodal model.
        
        Args:
            image_path: Path to chart thumbnail image
            spec: Vega-Lite spec (will be sanitized)
            prompt: Original user prompt used to generate the chart
            custom_instruction: Custom analysis instruction (optional)
            
        Returns:
            Analysis text from GLM model
        """
        # Verify image exists
        import os
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found at {image_path}")
        
        image_size = os.path.getsize(image_path)
        logger.info(f"Loading image from {image_path} ({image_size} bytes)")
        
        # Encode image to Base64
        image_base64 = self._encode_image_file(image_path)
        logger.info(f"Image encoded to Base64 (length={len(image_base64)})")
        
        # Sanitize spec to reduce size
        sanitized_spec = self._sanitize_spec(spec)
        
        # Build analysis instruction
        if custom_instruction:
            instruction = custom_instruction
        else:
            instruction = (
                "You are a data visualization expert. Analyze this chart and provide insights in **Markdown format**.\n\n"
                "Structure your response as follows:\n\n"
                "## 1. Chart Type & Visual Elements\n"
                "Describe the chart type and visual encodings.\n\n"
                "## 2. Data Insights\n"
                "Use **bold** for key findings and bullet points:\n"
                "- Finding 1\n"
                "- Finding 2\n\n"
                "## 3. Key Takeaways\n"
                "> Use blockquotes for important recommendations\n\n"
                "## 4. Recommendations\n"
                "Number your recommendations:\n"
                "1. Action item 1\n"
                "2. Action item 2\n"
            )
        
        # Build context
        context_parts = [f"Chart Specification:\n```json\n{sanitized_spec}\n```"]
        if prompt:
            context_parts.insert(0, f"User's Original Request: \"{prompt}\"")
        
        context = "\n\n".join(context_parts)
        
        # Construct messages
        messages = [
            {
                "role": "system",
                "content": instruction,
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_base64,
                        },
                    },
                    {
                        "type": "text",
                        "text": context,
                    },
                ],
            },
        ]
        
        logger.info(f"Calling GLM-4.5v for chart analysis (model={self.model}, image_size={image_size} bytes, has_image={bool(image_base64)})")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,  # Lower temperature for more focused analysis
                max_tokens=2000,
            )
            
            analysis_text = response.choices[0].message.content
            
            logger.info(f"GLM analysis complete, {len(analysis_text)} chars")
            return analysis_text.strip()
            
        except Exception as e:
            logger.error(f"GLM vision API call failed: {e}", exc_info=True)
            raise RuntimeError(f"GLM analysis failed: {e}") from e


# Singleton instance
_provider: Optional[GLMVisionProvider] = None


def get_vision_provider() -> GLMVisionProvider:
    """Get or create singleton GLM vision provider."""
    global _provider
    if _provider is None:
        _provider = GLMVisionProvider()
    return _provider
