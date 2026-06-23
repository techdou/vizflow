"""
Test script for validating improved prompt quality with 6-step reasoning.
Run this to check if DeepSeek generates better Vega-Lite specs.
"""

import asyncio
import json
from src.services.llm_provider import DeepSeekProvider

# Sample movie dataset preview
MOVIE_DATASET_PREVIEW = {
    "columns": ["title", "genre", "revenue", "rating", "year"],
    "sample_data": [
        {"title": "Movie A", "genre": "Action", "revenue": 500000000, "rating": 8.5, "year": 2020},
        {"title": "Movie B", "genre": "Comedy", "revenue": 200000000, "rating": 7.2, "year": 2021},
        {"title": "Movie C", "genre": "Action", "revenue": 750000000, "rating": 8.8, "year": 2019},
        {"title": "Movie D", "genre": "Drama", "revenue": 150000000, "rating": 8.0, "year": 2020},
        {"title": "Movie E", "genre": "Comedy", "revenue": 300000000, "rating": 7.5, "year": 2021},
    ],
    "filename": "movies.csv"
}

TEST_PROMPTS = [
    "哪一种电影最赚钱",
    "显示每种类型电影的平均评分",
    "展示收入前3的电影",
    "比较不同类型电影的数量",
]

async def test_prompt(provider: DeepSeekProvider, prompt: str, dataset_preview: dict):
    """Test a single prompt and display results."""
    print(f"\n{'='*80}")
    print(f"Testing prompt: {prompt}")
    print(f"{'='*80}")
    
    try:
        spec = await provider.generate_chart_spec(
            prompt=prompt,
            dataset_preview=dataset_preview
        )
        
        print("\n✅ Generated Vega-Lite Spec:")
        print(json.dumps(spec, indent=2, ensure_ascii=False))
        
        # Validate key fields
        if "$schema" in spec:
            print(f"\n✓ Schema: {spec['$schema']}")
        
        if "mark" in spec:
            print(f"✓ Mark type: {spec['mark']}")
        
        if "encoding" in spec:
            encodings = spec.get("encoding", {})
            print(f"✓ Encodings: {list(encodings.keys())}")
            
            # Check for aggregation
            for channel, enc in encodings.items():
                if "aggregate" in enc:
                    print(f"  - {channel}: {enc.get('field')} ({enc['aggregate']})")
                elif "field" in enc:
                    print(f"  - {channel}: {enc.get('field')} ({enc.get('type', 'unknown')})")
        
        if "data" in spec and "values" in spec["data"]:
            data_count = len(spec["data"]["values"])
            print(f"✓ Embedded data: {data_count} rows")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

async def main():
    """Run all prompt tests."""
    print("="*80)
    print("Testing Improved 6-Step Reasoning Prompt")
    print("="*80)
    
    provider = DeepSeekProvider()
    
    if not provider.enabled:
        print("\n⚠️  DeepSeek API not configured. Please set DEEPSEEK_API_KEY in .env")
        return
    
    results = []
    for prompt in TEST_PROMPTS:
        success = await test_prompt(provider, prompt, MOVIE_DATASET_PREVIEW)
        results.append((prompt, success))
        await asyncio.sleep(1)  # Rate limiting
    
    # Summary
    print("\n" + "="*80)
    print("Test Summary")
    print("="*80)
    for prompt, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {prompt}")
    
    success_rate = sum(1 for _, s in results if s) / len(results) * 100
    print(f"\nSuccess rate: {success_rate:.0f}%")

if __name__ == "__main__":
    asyncio.run(main())
