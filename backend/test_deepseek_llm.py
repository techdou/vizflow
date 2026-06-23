"""
测试真实 DeepSeek LLM 集成
"""
import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from src.services.llm_provider import generate_chart_spec


async def test_deepseek():
    """测试 DeepSeek API 生成图表"""
    
    print("\n=== 测试 DeepSeek LLM 图表生成 ===\n")
    
    # 测试数据预览
    dataset_preview = {
        "columns": ["category", "value"],
        "sample_data": [
            {"category": "A", "value": "28"},
            {"category": "B", "value": "55"},
            {"category": "C", "value": "43"},
            {"category": "D", "value": "91"},
            {"category": "E", "value": "81"}
        ],
        "filename": "test_data.csv",
        "mime_type": "text/csv"
    }
    
    prompt = "创建一个柱状图，显示每个类别的值"
    
    print(f"数据预览: {dataset_preview['filename']}")
    print(f"列: {dataset_preview['columns']}")
    print(f"Prompt: {prompt}\n")
    
    try:
        print("🔄 调用 DeepSeek API...")
        spec = await generate_chart_spec(
            dataset_id="test-001",
            prompt=prompt,
            dataset_preview=dataset_preview
        )
        
        print("\n✅ 成功生成 Vega-Lite spec!")
        print(f"\n图表类型: {spec.get('mark', 'unknown')}")
        print(f"Schema: {spec.get('$schema', 'unknown')}")
        
        if 'encoding' in spec:
            print(f"\n编码通道:")
            for channel, config in spec['encoding'].items():
                field = config.get('field', '?')
                type_ = config.get('type', '?')
                print(f"  - {channel}: {field} ({type_})")
        
        # 打印完整 spec
        import json
        print(f"\n完整 Spec:")
        print(json.dumps(spec, indent=2, ensure_ascii=False))
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_deepseek())
    sys.exit(0 if success else 1)
