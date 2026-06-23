"""
Quick smoke test for VizFlow backend
"""

import requests
import json
import sys

BASE_URL = "http://127.0.0.1:8000"

def test_health():
    """Test health endpoint"""
    print("Testing /health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    assert response.status_code == 200
    data = response.json()
    print(f"✓ Health check OK: {data}")
    return True

def test_upload_dataset():
    """Test dataset upload"""
    print("\nTesting POST /api/datasets...")
    
    # Create a simple CSV content
    csv_content = "name,value\nA,10\nB,20\nC,30"
    files = {'file': ('test.csv', csv_content, 'text/csv')}
    
    response = requests.post(f"{BASE_URL}/api/datasets", files=files)
    assert response.status_code == 200
    data = response.json()
    dataset_id = data['dataset_id']
    print(f"✓ Dataset uploaded: {dataset_id}")
    return dataset_id

def test_generate_chart(dataset_id):
    """Test chart generation"""
    print(f"\nTesting POST /api/charts with dataset_id={dataset_id}...")
    
    payload = {
        "dataset_id": dataset_id,
        "prompt": "Show a bar chart"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/charts",
        json=payload,
        headers={'Content-Type': 'application/json'}
    )
    
    assert response.status_code == 200
    data = response.json()
    chart_spec_id = data['chart_spec_id']
    print(f"✓ Chart generated: {chart_spec_id}")
    print(f"  Spec preview: {json.dumps(data['node_payload']['spec_json'], indent=2)[:200]}...")
    return chart_spec_id

def main():
    print("=== VizFlow Backend Smoke Test ===\n")
    
    try:
        # Test 1: Health
        test_health()
        
        # Test 2: Upload
        dataset_id = test_upload_dataset()
        
        # Test 3: Generate chart
        chart_spec_id = test_generate_chart(dataset_id)
        
        print("\n=== All tests passed! ✓ ===")
        return 0
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return 1
    except requests.exceptions.ConnectionError:
        print("\n✗ Cannot connect to backend. Is it running on http://127.0.0.1:8000?")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
