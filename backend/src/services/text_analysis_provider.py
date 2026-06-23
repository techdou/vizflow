"""
DeepSeek text-based chart analysis provider.

Unlike the GLM vision provider (which consumes a rendered thumbnail image),
this provider analyzes a chart from its Vega-Lite spec + underlying data
using the DeepSeek text model. This removes the hard dependency on a vision
API key while still producing structured Markdown insights.
"""
import json
import logging
from typing import Optional, Any
from openai import AsyncOpenAI

from ..core.config import settings

logger = logging.getLogger(__name__)


class DeepSeekAnalysisProvider:
    """DeepSeek-based text analysis provider for chart insight generation."""

    def __init__(self):
        if settings.DEEPSEEK_API_KEY and settings.DEEPSEEK_API_KEY != "your_key_here":
            self.client = AsyncOpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL,
                timeout=settings.ANALYSIS_TIMEOUT,
                max_retries=2,
            )
            self.enabled = True
        else:
            self.client = None
            self.enabled = False
            logger.warning("DeepSeek API key not configured, analysis will be limited")

    def _summarize_data(self, spec: dict[str, Any]) -> dict[str, Any]:
        """
        Build a compact statistical summary of the chart's data so the LLM
        can reason about real numbers without sending the full dataset.

        Returns a dict with: row_count, fields, stats {field: {min,max,mean,...}},
        top_category_values (categorical distribution), sample_rows.
        """
        values = []
        if isinstance(spec.get("data"), dict):
            values = spec["data"].get("values", []) or []
        elif isinstance(spec.get("data"), list):
            values = spec["data"]

        summary: dict[str, Any] = {
            "row_count": len(values),
            "fields": list(values[0].keys()) if values else [],
            "sample_rows": values[:5],
        }

        if not values:
            return summary

        fields = summary["fields"]
        stats: dict[str, Any] = {}
        for field in fields:
            col_vals = [row.get(field) for row in values if row.get(field) not in (None, "", "N/A")]
            if not col_vals:
                continue
            # Try numeric
            try:
                nums = [float(v) for v in col_vals]
                sorted_nums = sorted(nums)
                stats[field] = {
                    "type": "quantitative",
                    "min": sorted_nums[0],
                    "max": sorted_nums[-1],
                    "mean": round(sum(nums) / len(nums), 4),
                    "count": len(nums),
                }
            except (ValueError, TypeError):
                # Categorical distribution
                dist: dict[str, int] = {}
                for v in col_vals:
                    key = str(v)
                    dist[key] = dist.get(key, 0) + 1
                # Top 8 categories
                top = sorted(dist.items(), key=lambda kv: kv[1], reverse=True)[:8]
                stats[field] = {
                    "type": "categorical",
                    "unique": len(dist),
                    "top_values": dict(top),
                }
        summary["stats"] = stats
        return summary

    def _describe_spec(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Extract the visual structure (mark, encoding, transform) from the spec."""
        desc: dict[str, Any] = {
            "mark": spec.get("mark"),
            "encoding": spec.get("encoding", {}),
        }
        if spec.get("transform"):
            desc["transform"] = spec["transform"]
        return desc

    async def analyze_chart(
        self,
        spec: dict[str, Any],
        prompt: Optional[str] = None,
        custom_instruction: Optional[str] = None,
    ) -> str:
        """
        Analyze a chart (from its spec + data) and return structured Markdown.

        Args:
            spec: Vega-Lite spec (with embedded data).
            prompt: Original user prompt that produced this chart.
            custom_instruction: Optional override for the analysis instruction.

        Returns:
            Markdown analysis text.
        """
        if not self.enabled:
            return (
                "## 分析不可用\n\n未配置 DeepSeek API key，无法生成 AI 分析。"
                "请在 `backend/.env` 中设置 `DEEPSEEK_API_KEY`。"
            )

        data_summary = self._summarize_data(spec)
        spec_desc = self._describe_spec(spec)

        instruction = custom_instruction or (
            "你是一位数据可视化分析专家。请基于给定的图表规范与数据统计，"
            "用**中文 Markdown** 输出结构化的图表洞察报告。\n\n"
            "请严格按以下结构输出：\n\n"
            "## 1. 图表类型与视觉编码\n"
            "描述图表类型（柱状图/折线图/饼图等）以及 x、y、color 等编码通道。\n\n"
            "## 2. 数据洞察\n"
            "结合统计数字给出**加粗**的关键发现，使用要点列表：\n"
            "- 发现 1（含具体数值）\n"
            "- 发现 2\n\n"
            "## 3. 关键结论\n"
            "> 用引用块给出最重要的 1-2 条结论\n\n"
            "## 4. 建议与改进\n"
            "用编号列表给出可执行的改进建议：\n"
            "1. 建议 1\n"
            "2. 建议 2\n\n"
            "要求：结论必须基于提供的数据统计，避免编造未给出的数字；"
            "若数据不足，请明确说明。"
        )

        context_parts = []
        if prompt:
            context_parts.append(f"用户原始需求：\"{prompt}\"")
        context_parts.append(f"图表规范（视觉结构）：\n```json\n{json.dumps(spec_desc, ensure_ascii=False, indent=2)}\n```")
        context_parts.append(f"数据统计摘要：\n```json\n{json.dumps(data_summary, ensure_ascii=False, indent=2)}\n```")
        context = "\n\n".join(context_parts)

        messages = [
            {"role": "system", "content": instruction},
            {"role": "user", "content": context},
        ]

        logger.info(f"Calling DeepSeek text analysis (rows={data_summary['row_count']}, fields={data_summary['fields']})")

        try:
            response = await self.client.chat.completions.create(
                model=settings.DEEPSEEK_MODEL,
                messages=messages,
                temperature=0.3,
                max_tokens=2000,
            )
            text = response.choices[0].message.content or ""
            text = text.strip()
            logger.info(f"DeepSeek analysis complete, {len(text)} chars")
            return text if text else "## 分析结果为空\n\n模型未返回有效内容，请重试。"
        except Exception as e:
            logger.error(f"DeepSeek analysis failed: {e}", exc_info=True)
            raise RuntimeError(f"DeepSeek analysis failed: {e}") from e


# Singleton
_provider: Optional[DeepSeekAnalysisProvider] = None


def get_text_analysis_provider() -> DeepSeekAnalysisProvider:
    global _provider
    if _provider is None:
        _provider = DeepSeekAnalysisProvider()
    return _provider
