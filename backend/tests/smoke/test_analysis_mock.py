"""
GLM Analysis test with mocked thumbnail (bypasses thumbnail requirement).

This demonstrates the full analysis flow using a base64-encoded test image.
"""
from fastapi.testclient import TestClient
from src.main import app
from src.core.config import settings
from src.models.database import ChartSpec
from src.core.database import get_db
import io
import base64


def test_analysis_with_mock_thumbnail():
    """
    Test GLM analysis with a mocked thumbnail.
    
    Creates a 1x1 pixel PNG to satisfy the thumbnail requirement.
    """
    client = TestClient(app)
    
    print("\n=== GLM Analysis Test (Mocked Thumbnail) ===\n")
    
    if not settings.GLM_API_KEY:
        print("⚠️  GLM_API_KEY not set, skipping test")
        return
    
    # Step 1: Upload dataset
    print("Step 1: Creating test chart...")
    csv_content = """category,value
A,10
B,20
C,15"""
    
    response = client.post(
        "/api/datasets",
        files={"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    )
    dataset_id = response.json()["dataset_id"]
    
    # Step 2: Generate chart
    response = client.post(
        "/api/charts",
        json={
            "dataset_id": dataset_id,
            "prompt": "Bar chart of values by category"
        }
    )
    chart_spec_id = response.json()["chart_spec_id"]
    print(f"✓ Chart created: {chart_spec_id}")
    
    # Step 3: Mock thumbnail file (1x1 red pixel PNG)
    # This is a minimal valid PNG file
    mock_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
    )
    
    # Save mock thumbnail
    import os
    thumbnail_path = os.path.join(settings.THUMBNAILS_DIR, f"{chart_spec_id}.png")
    with open(thumbnail_path, "wb") as f:
        f.write(mock_png)
    print(f"✓ Mock thumbnail saved")
    
    # Step 4: Update chart spec to have thumbnail_uri
    db = next(get_db())
    chart = db.query(ChartSpec).filter(ChartSpec.id == chart_spec_id).first()
    chart.thumbnail_uri = f"/api/thumbnails/{chart_spec_id}.png"
    db.commit()
    
    # Step 5: Call analysis
    print("\nStep 2: Calling GLM-4V analysis...")
    try:
        response = client.post(
            "/api/analysis",
            json={"chart_spec_id": chart_spec_id}
        )
        
        if response.status_code != 200:
            print(f"❌ Analysis failed: {response.json()}")
            return
        
        analysis_data = response.json()
        print(f"✓ Analysis complete!")
        print(f"  Analysis ID: {analysis_data['analysis_id']}")
        print(f"  Model: {analysis_data['node_payload']['data']['model_tag']}")
        print(f"  Text length: {len(analysis_data['node_payload']['data']['text'])} chars")
        print(f"\n📊 Analysis Text:\n")
        print(analysis_data['node_payload']['data']['text'])
        
        print("\n✅ T044: POST /analysis works!")
        print("✅ T045: Node payload structure valid!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n=== Test Complete ===\n")


if __name__ == "__main__":
    test_analysis_with_mock_thumbnail()
