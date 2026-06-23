"""
Smoke tests for VizFlow API (T012-T014)
"""
import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_upload_dataset():
    """T012: POST /datasets → dataset_id"""
    print("\n=== T012: Testing POST /datasets ===")
    with open("test_data.csv", "rb") as f:
        response = requests.post(
            f"{BASE_URL}/api/datasets",
            files={"file": ("test_data.csv", f, "text/csv")}
        )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert "dataset_id" in data, "Missing dataset_id in response"
    
    print("✓ T012 PASSED")
    return data["dataset_id"]


def test_generate_chart(dataset_id):
    """T013: POST /charts → spec valid & thumbnail stored"""
    print("\n=== T013: Testing POST /charts ===")
    response = requests.post(
        f"{BASE_URL}/api/charts",
        json={
            "dataset_id": dataset_id,
            "prompt": "创建一个柱状图显示每个类别的值"
        }
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert "chart_spec_id" in data, "Missing chart_spec_id"
    assert "node_payload" in data, "Missing node_payload"
    
    node = data["node_payload"]
    assert node["type"] == "chart", f"Expected chart node, got {node['type']}"
    assert "vega_lite_spec" in node["data"], "Missing vega_lite_spec in node data"
    
    print("✓ T013 PASSED")
    return data


if __name__ == "__main__":
    try:
        # Test upload
        dataset_id = test_upload_dataset()
        
        # Test chart generation
        chart_data = test_generate_chart(dataset_id)
        
        print("\n=== ALL SMOKE TESTS PASSED ===")
        print(f"\nDataset ID: {dataset_id}")
        print(f"Chart Spec ID: {chart_data['chart_spec_id']}")
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
