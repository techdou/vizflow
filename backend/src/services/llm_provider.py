"""
LLM provider adapter for chart generation and analysis.
Integrates with DeepSeek (chart generation) and GLM (multimodal analysis) using OpenAI SDK.

Thread-safety note:
    DeepSeekProvider is a module-level singleton, so _call_api MUST NOT store any
    per-request state on self. All per-request data (full dataset, prompt) is passed
    through explicit local variables / return values to avoid cross-request races.
"""

import json
import re
from typing import Optional, Dict, Any, List, Tuple
from openai import AsyncOpenAI
from src.core.config import settings
from src.core.logging import logger

# Example Vega-Lite spec for demo / fallback
EXAMPLE_SPEC = {
    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
    "description": "A simple bar chart with embedded data.",
    "data": {
        "values": [
            {"category": "A", "value": 28},
            {"category": "B", "value": 55},
            {"category": "C", "value": 43},
            {"category": "D", "value": 91},
            {"category": "E", "value": 81}
        ]
    },
    "mark": "bar",
    "encoding": {
        "x": {"field": "category", "type": "nominal", "axis": {"labelAngle": 0}},
        "y": {"field": "value", "type": "quantitative"}
    }
}

# Max rows to embed in the generated Vega-Lite spec. Larger datasets are sampled
# to keep the spec (and downstream analysis) tractable.
MAX_SPEC_ROWS = 500


def _sample_rows(rows: List[dict], n: int) -> List[dict]:
    """Deterministic stride sampling: evenly pick n rows preserving order."""
    if not rows or n <= 0:
        return []
    if len(rows) <= n:
        return list(rows)
    step = len(rows) / n
    return [rows[int(i * step)] for i in range(n)]


def _extract_json_object(content: str) -> Optional[dict]:
    """
    Robustly extract the first valid JSON object from an LLM response.

    Tries, in order:
      1. ```json ... ``` fenced code block
      2. ``` ... ``` fenced code block
      3. Scan candidate `{` positions and use json.JSONDecoder.raw_decode
         to find the first well-formed object (handles strings containing
         braces, unlike naive brace counting).
    Returns None if nothing parses.
    """
    if not content:
        return None

    # 1. Fenced ```json block
    m = re.search(r"```json\s*\n(.*?)```", content, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 2. Any fenced block
    m = re.search(r"```\s*\n(.*?)```", content, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 3. Walk every '{' and ask the decoder how far the object extends.
    #    This correctly skips braces inside JSON string values.
    decoder = json.JSONDecoder()
    for i, ch in enumerate(content):
        if ch != "{":
            continue
        try:
            obj, _end = decoder.raw_decode(content[i:])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


class DeepSeekProvider:
    """DeepSeek LLM provider for chart generation using OpenAI SDK."""

    def __init__(self):
        if settings.DEEPSEEK_API_KEY and settings.DEEPSEEK_API_KEY != "your_key_here":
            self.client = AsyncOpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL,
                timeout=settings.CHART_GENERATION_TIMEOUT,  # Set default timeout
                max_retries=2  # Reduce retries to avoid excessive waiting
            )
            self.enabled = True
        else:
            self.client = None
            self.enabled = False
            logger.warning("DeepSeek API key not configured, using placeholder specs")

    # NOTE: no per-request state is stored on self anywhere below this point.

    def _infer_column_types(self, columns: list, sample_data: list) -> list:
        """
        Infer Vega-Lite field types from sample data.
        Returns list of types: quantitative, nominal, temporal, or ordinal
        """
        types = []

        for col in columns:
            if not sample_data:
                types.append("nominal")
                continue

            # Get non-empty values for this column
            values = [row.get(col) for row in sample_data if row.get(col) not in (None, "", "N/A")]

            if not values:
                types.append("nominal")
                continue

            # Check if all values are numeric
            try:
                numeric_values = [float(v) for v in values]
                # If numbers are small integers (< 20 unique values), might be ordinal/nominal
                unique_count = len(set(numeric_values))
                if unique_count <= 10 and all(v == int(v) for v in numeric_values):
                    types.append("ordinal")  # Likely categorical with order
                else:
                    types.append("quantitative")
            except (ValueError, TypeError):
                # Check for date/time patterns
                sample_val = str(values[0]).lower()
                if any(pattern in sample_val for pattern in ["date", "time", "year", "month", "-", "/"]):
                    types.append("temporal")
                else:
                    types.append("nominal")

        return types

    async def generate_chart_spec(
        self,
        prompt: Optional[str] = None,
        dataset_preview: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate Vega-Lite spec using DeepSeek LLM."""
        if not self.enabled:
            logger.info("DeepSeek disabled, returning example spec")
            return EXAMPLE_SPEC

        try:
            return await self._call_api(prompt, dataset_preview)
        except Exception as e:
            logger.error(f"DeepSeek API call failed: {e}, falling back to example spec", exc_info=True)
            return EXAMPLE_SPEC

    async def _call_api(
        self,
        prompt: Optional[str],
        dataset_preview: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Call DeepSeek API. Per-request state is kept strictly local (race-safe)."""

        # Build system prompt with step-by-step reasoning
        system_prompt = """You are a data visualization expert. Generate Vega-Lite v5 JSON specifications following a structured reasoning process.

Your task: Given a table and user instruction, reason through the visualization step-by-step, then output a valid Vega-Lite v5 spec.

**Reasoning Steps (follow this order):**

Step 1. Select the columns:
- Identify which columns from the table are needed for the visualization
- Consider the user's instruction to determine relevant fields

Step 2. Filter the data:
- Determine if any data filtering is needed (e.g., top N, value ranges, specific categories)
- Specify filter conditions if applicable

Step 3. Add aggregate functions:
- Decide if aggregation is needed (count, sum, mean, median, min, max)
- Identify the aggregation field and grouping dimension

Step 4. Choose chart type:
- Select appropriate mark: bar (comparison), line (trend), area (trend with volume), point (scatter), arc (proportion), etc.
- Consider: comparison → bar, trend over time → line, distribution → histogram, proportion → pie/arc

Step 5. Select encodings:
- Map fields to visual channels: x, y, color, size, etc.
- Specify field types: quantitative (numbers), nominal (categories), temporal (dates), ordinal (ordered)
- Add sorting if needed (e.g., sort by value descending)

Step 6. Sort the data:
- Determine sort order if visualization benefits from it (e.g., ranking, top N)
- Specify sort field and direction

**Response Format:**
1. Brief reasoning (2-4 sentences covering the 6 steps)
2. The Vega-Lite JSON spec (wrapped in ```json code block)

**Vega-Lite Spec Requirements:**
- Include $schema: "https://vega.github.io/schema/vega-lite/v5.json"
- Use embedded data format: "data": {"values": [...]}
- Include at least the example rows shown, system will inject full dataset automatically
- Use transform for filtering/calculations when needed
- Apply sorting in encoding with "sort" property
- Keep spec clean and readable

**Example Response:**

Step 1-2: Select revenue and category columns, no filtering needed.
Step 3-4: Aggregate sum of revenue by category, use bar chart for comparison.
Step 5-6: Map category to x-axis (nominal), sum(revenue) to y-axis (quantitative), sort descending by revenue.

```json
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "data": {"values": [{"category": "A", "revenue": 100}]},
  "mark": "bar",
  "encoding": {
    "x": {
      "field": "category",
      "type": "nominal",
      "sort": "-y",
      "axis": {"title": "Category"}
    },
    "y": {
      "field": "revenue",
      "type": "quantitative",
      "aggregate": "sum",
      "axis": {"title": "Total Revenue"}
    }
  }
}
```

**Advanced Features:**
- For top N: use transform with window and filter
- For time series: ensure temporal type and proper time axis
- For proportions: use arc mark with theta encoding
- For grouped comparisons: add color encoding for subcategories"""

        # ---- Build user prompt; all per-request data is LOCAL ----
        user_parts: List[str] = []
        full_dataset: Optional[List[dict]] = None  # local only, NOT self._full_dataset

        if dataset_preview and "sample_data" in dataset_preview:
            columns = dataset_preview.get("columns", [])
            all_data = dataset_preview["sample_data"]  # All available data
            filename = dataset_preview.get("filename", "data")

            # Capture full dataset locally for post-injection (race-safe).
            full_dataset = all_data

            # Use first 10 rows for type inference (more accurate)
            inference_sample = all_data[:min(10, len(all_data))]
            column_types = self._infer_column_types(columns, inference_sample)

            # Format table input
            table_name = re.sub(r"\.(csv|json)$", "", filename).replace("_", " ").title()
            table_header = ",".join(columns)
            table_header_types = ",".join(column_types)

            # Format sample rows (show only 5 examples to save tokens)
            sample_rows = []
            display_count = min(5, len(all_data))
            for row in all_data[:display_count]:
                row_values = [str(row.get(col, "")) for col in columns]
                sample_rows.append(",".join(row_values))
            table_data_example = "\n".join(sample_rows)

            user_parts.append(f"""### Table Input:
Table Name: {table_name}
Table Header: {table_header}
Table Header Type: {table_header_types}
Total Rows: {len(all_data)}
Table Data Example (first {display_count} rows):
{table_data_example}""")

        # Add user instruction
        if prompt:
            user_parts.insert(0, f"### Instruction:\n{prompt}")
        else:
            user_parts.insert(0, "### Instruction:\nCreate an appropriate visualization to explore this dataset.")

        user_parts.append("""
### Response:
Follow the 6-step reasoning process:
Step 1. Select the columns
Step 2. Filter the data
Step 3. Add aggregate functions
Step 4. Choose chart type
Step 5. Select encodings
Step 6. Sort the data

Then provide the Vega-Lite JSON spec in a ```json code block.""")

        user_prompt = "\n\n".join(user_parts)

        # Call API using OpenAI SDK
        logger.info(f"Calling DeepSeek API: model={settings.DEEPSEEK_MODEL}")
        logger.debug(f"Prompt columns: {columns if dataset_preview else 'N/A'}")
        logger.debug(f"User instruction: {prompt or 'auto visualization'}")

        response = await self.client.chat.completions.create(
            model=settings.DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,  # Lower temperature for more focused reasoning
            max_tokens=2500  # Increased for 6-step analysis + spec
            # timeout is set in client initialization
        )

        content = (response.choices[0].message.content or "").strip()

        # Robust extraction (fix #14): handles JSON strings containing braces.
        spec = _extract_json_object(content)
        if spec is None:
            logger.error(f"Failed to parse JSON from response. Full response: {content[:1000]}...")
            raise ValueError("No valid JSON object found in LLM response")

        # Inject full dataset locally (race-safe). Cap rows on big tables (fix #13).
        if full_dataset and isinstance(spec.get("data"), dict):
            original_count = len(spec["data"].get("values", []) or [])
            if len(full_dataset) > MAX_SPEC_ROWS:
                injected = _sample_rows(full_dataset, MAX_SPEC_ROWS)
                spec["data"]["values"] = injected
                logger.info(
                    f"Injected sampled dataset: {len(injected)} rows "
                    f"(source {len(full_dataset)} rows > cap {MAX_SPEC_ROWS}, was {original_count} rows)"
                )
            else:
                spec["data"]["values"] = full_dataset
                logger.info(f"Injected full dataset: {len(full_dataset)} rows (was {original_count} rows)")

        # Log the generated spec summary
        mark_type = spec.get("mark", "unknown")
        encodings = spec.get("encoding", {})
        data_count = len(spec.get("data", {}).get("values", []) or [])

        logger.info(
            f"Successfully generated Vega-Lite spec from DeepSeek: "
            f"mark={mark_type}, encodings={list(encodings.keys()) if isinstance(encodings, dict) else encodings}, "
            f"data_rows={data_count}"
        )

        # Validate essential fields
        if "$schema" not in spec:
            logger.warning("Generated spec missing $schema, adding it")
            spec["$schema"] = "https://vega.github.io/schema/vega-lite/v5.json"

        if "data" not in spec or not spec["data"].get("values"):
            logger.warning("Generated spec has no embedded data, this may cause rendering issues")

        return spec


# Global singleton instance
_deepseek_provider = DeepSeekProvider()


async def generate_chart_spec(
    dataset_id: str,
    prompt: Optional[str] = None,
    dataset_preview: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generate Vega-Lite spec using LLM.

    Args:
        dataset_id: ID of the dataset
        prompt: User's natural language prompt
        dataset_preview: Sample rows and schema from dataset

    Returns:
        Vega-Lite JSON spec
    """
    logger.info(f"Generating chart spec for dataset_id={dataset_id} with prompt='{prompt}'")
    return await _deepseek_provider.generate_chart_spec(prompt, dataset_preview)

def validate_vega_lite_spec(spec: dict) -> Tuple[bool, Optional[str]]:
    """
    Validate Vega-Lite spec against minimal rules.

    Returns:
        (is_valid, error_message)
    """

    # Basic validation
    if not isinstance(spec, dict):
        return False, "Spec must be a JSON object"

    if "$schema" not in spec:
        return False, "Missing $schema field"

    if "mark" not in spec and "layer" not in spec:
        return False, "Missing mark or layer field"

    # Check for forbidden features
    if "data" in spec and isinstance(spec["data"], dict):
        if "url" in spec["data"]:
            return False, "External data URLs are forbidden for security"

    return True, None
