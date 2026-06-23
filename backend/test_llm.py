"""
Test real DeepSeek LLM integration
"""
import requests
import json

BASE_URL = "http://127.0.0.1:8000/api"

# Clear cache by using a different prompt
test_cases = [
    {
        "file": "sales_test.csv",
        "prompt": "Create a line chart showing sales trend over months"
    },
    {
        "file": "sales_test.csv",
        "prompt": "Show monthly sales as a bar chart"
    }
]

for i, test in enumerate(test_cases):
    print(f"\n=== Test {i+1}: {test['prompt']} ===")
    
    # Upload dataset
    with open(test['file'], 'rb') as f:
        upload_resp = requests.post(
            f"{BASE_URL}/datasets",
            files={"file": (test['file'], f, "text/csv")}
        )
    
    if upload_resp.status_code != 200:
        print(f"Upload failed: {upload_resp.text}")
        continue
    
    dataset_id = upload_resp.json()["dataset_id"]
    print(f"Dataset ID: {dataset_id}")
    
    # Generate chart with real LLM
    chart_resp = requests.post(
        f"{BASE_URL}/charts",
        json={
            "dataset_id": dataset_id,
            "prompt": test['prompt']
        }
    )
    
    if chart_resp.status_code != 200:
        print(f"Chart generation failed: {chart_resp.text}")
        continue
    
    data = chart_resp.json()
    print(f"Chart ID: {data['chart_spec_id']}")
    
    spec = data['node_payload']['data']['vega_lite_spec']
    print(f"\nGenerated Spec:")
    print(json.dumps(spec, indent=2))
    
    # Verify it's not the placeholder
    if spec.get('description') == "A simple bar chart with embedded data.":
        print("\n⚠️  WARNING: Still using placeholder spec!")
    else:
        print("\n✅ Real LLM spec generated!")
