"""
T025: Smoke test for chart generation caching
Test that same dataset+prompt returns cached result with same chart_spec_id
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000/api"

def test_cache_behavior():
    """Test cache hit and miss scenarios"""
    
    print("\n=== T025: Testing Chart Generation Cache ===\n")
    
    # Upload a test dataset
    print("Step 1: Uploading test dataset...")
    test_csv_content = """name,value,category
Item A,100,Type1
Item B,200,Type1
Item C,150,Type2
Item D,300,Type2
"""
    
    files = {'file': ('test_cache.csv', test_csv_content, 'text/csv')}
    response = requests.post(f"{BASE_URL}/datasets", files=files)
    
    if response.status_code != 200:
        print(f"❌ Failed to upload dataset: {response.status_code}")
        print(response.text)
        return False
    
    dataset_id = response.json()['dataset_id']
    print(f"✓ Dataset uploaded: {dataset_id}")
    
    # Test 1: Generate chart with prompt "test prompt 1"
    print("\nStep 2: First generation (should miss cache)...")
    prompt1 = "显示每个类别的平均值"
    
    payload1 = {
        "dataset_id": dataset_id,
        "prompt": prompt1
    }
    
    start_time = time.time()
    response1 = requests.post(f"{BASE_URL}/charts", json=payload1)
    elapsed1 = time.time() - start_time
    
    if response1.status_code != 200:
        print(f"❌ First generation failed: {response1.status_code}")
        print(response1.text)
        return False
    
    result1 = response1.json()
    chart_spec_id1 = result1['chart_spec_id']
    print(f"✓ First generation successful: {chart_spec_id1}")
    print(f"  Time: {elapsed1:.2f}s")
    
    # Test 2: Same request (should hit cache)
    print("\nStep 3: Second generation with SAME prompt (should hit cache)...")
    
    start_time = time.time()
    response2 = requests.post(f"{BASE_URL}/charts", json=payload1)
    elapsed2 = time.time() - start_time
    
    if response2.status_code != 200:
        print(f"❌ Second generation failed: {response2.status_code}")
        return False
    
    result2 = response2.json()
    chart_spec_id2 = result2['chart_spec_id']
    
    if chart_spec_id2 == chart_spec_id1:
        print(f"✓ Cache HIT: Same chart_spec_id returned ({chart_spec_id2})")
        print(f"  Time: {elapsed2:.2f}s (should be faster)")
        
        if elapsed2 < elapsed1 * 0.5:  # Cache should be at least 2x faster
            print("✓ Cache response is significantly faster")
        else:
            print("⚠️  Cache response not significantly faster (may still be valid)")
    else:
        print(f"❌ Cache MISS: Different chart_spec_id")
        print(f"  First:  {chart_spec_id1}")
        print(f"  Second: {chart_spec_id2}")
        return False
    
    # Test 3: Different prompt (should miss cache)
    print("\nStep 4: Third generation with DIFFERENT prompt (should miss cache)...")
    
    payload3 = {
        "dataset_id": dataset_id,
        "prompt": "显示每个类别的总和"  # Different prompt
    }
    
    response3 = requests.post(f"{BASE_URL}/charts", json=payload3)
    
    if response3.status_code != 200:
        print(f"❌ Third generation failed: {response3.status_code}")
        return False
    
    result3 = response3.json()
    chart_spec_id3 = result3['chart_spec_id']
    
    if chart_spec_id3 != chart_spec_id1:
        print(f"✓ Cache MISS (expected): New chart_spec_id ({chart_spec_id3})")
    else:
        print(f"❌ Cache HIT (unexpected): Should create new spec for different prompt")
        return False
    
    print("\n✓ T025 PASSED: Cache behavior correct\n")
    return True

if __name__ == "__main__":
    try:
        success = test_cache_behavior()
        if success:
            print("="*60)
            print("ALL CACHE TESTS PASSED")
            print("="*60)
        else:
            print("="*60)
            print("CACHE TESTS FAILED")
            print("="*60)
            exit(1)
    except Exception as e:
        print(f"\n❌ Test execution error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
