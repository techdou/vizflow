"""
端到端测试: 上传数据集 → 调用真实 DeepSeek API 生成图表
"""
import requests
import json

BASE_URL = "http://127.0.0.1:8000/api"

def test_end_to_end():
    """完整流程测试"""
    
    print("\n=== 端到端测试: 真实 LLM 图表生成 ===\n")
    
    # Step 1: 上传数据集
    print("📤 步骤 1: 上传数据集...")
    with open("test_data.csv", "rb") as f:
        response = requests.post(
            f"{BASE_URL}/datasets",
            files={"file": ("sales_data.csv", f, "text/csv")}
        )
    
    if response.status_code != 200:
        print(f"❌ 上传失败: {response.status_code}")
        print(response.text)
        return False
    
    dataset_data = response.json()
    dataset_id = dataset_data["dataset_id"]
    print(f"✅ 数据集上传成功: {dataset_id}\n")
    
    # Step 2: 使用真实 LLM 生成图表
    print("🤖 步骤 2: 调用 DeepSeek API 生成图表...")
    
    prompts = [
        "创建一个柱状图显示每个类别的值",
        "用折线图展示趋势",
        "生成一个简洁的可视化"
    ]
    
    for i, prompt in enumerate(prompts, 1):
        print(f"\n--- 测试 {i}: {prompt} ---")
        
        response = requests.post(
            f"{BASE_URL}/charts",
            json={
                "dataset_id": dataset_id,
                "prompt": prompt
            }
        )
        
        if response.status_code != 200:
            print(f"❌ 生成失败: {response.status_code}")
            print(response.text)
            continue
        
        chart_data = response.json()
        chart_spec_id = chart_data["chart_spec_id"]
        node_payload = chart_data["node_payload"]
        
        print(f"✅ 图表生成成功: {chart_spec_id}")
        
        spec = node_payload["data"]["vega_lite_spec"]
        print(f"   图表类型: {spec.get('mark', 'unknown')}")
        
        if "encoding" in spec:
            print(f"   编码通道:")
            for channel, config in spec["encoding"].items():
                field = config.get("field", "?")
                type_ = config.get("type", "?")
                print(f"     - {channel}: {field} ({type_})")
    
    print("\n=== 所有测试完成 ===")
    return True


if __name__ == "__main__":
    try:
        success = test_end_to_end()
        print(f"\n{'✅ 测试通过' if success else '❌ 测试失败'}")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
