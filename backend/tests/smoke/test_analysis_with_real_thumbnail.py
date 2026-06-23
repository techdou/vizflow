"""
End-to-end test: Upload -> Generate Chart -> Analyze
Tests the complete workflow with real thumbnail generation using vl-convert.
"""
import sys
import os
import io

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from core.database import SessionLocal
from models.database import Dataset, ChartSpec, Analysis
from services.chart_generator import generate_chart_spec
from services.thumbnails import generate_thumbnail
from storage.files import save_thumbnail
from services.vision_provider import get_vision_provider
from core.config import settings


def test_full_analysis_workflow():
    """Test complete workflow: dataset -> chart -> thumbnail -> analysis"""
    
    db = SessionLocal()
    
    try:
        print("\n=== Step 1: Create test dataset ===")
        
        # Create a test dataset in memory
        csv_content = "category,value\nA,28\nB,55\nC,43"
        csv_bytes = csv_content.encode('utf-8')
        
        dataset = Dataset(
            id="test-dataset-analysis",
            name="test-data.csv",
            mime="text/csv",
            size_bytes=len(csv_bytes),
            storage_path=f"data/uploads/test-dataset-analysis.csv"
        )
        
        # Save CSV to disk
        os.makedirs(os.path.dirname(dataset.storage_path), exist_ok=True)
        with open(dataset.storage_path, 'wb') as f:
            f.write(csv_bytes)
        
        db.add(dataset)
        db.commit()
        print(f"✓ Dataset created: {dataset.id}")
        
        
        print("\n=== Step 2: Generate chart spec ===")
        
        spec = generate_chart_spec(dataset.id, "Show a bar chart")
        print(f"✓ Chart spec generated")
        print(f"  Mark: {spec.get('mark')}")
        
        # Save chart spec to database
        chart_spec = ChartSpec(
            id="test-chart-analysis",
            dataset_id=dataset.id,
            prompt="Show a bar chart",
            spec_json=spec,
            thumbnail_uri=None  # Will be set after thumbnail generation
        )
        db.add(chart_spec)
        db.commit()
        print(f"✓ Chart spec saved: {chart_spec.id}")
        
        
        print("\n=== Step 3: Generate thumbnail ===")
        
        thumbnail_bytes = generate_thumbnail(spec, chart_spec.id)
        print(f"✓ Thumbnail generated: {len(thumbnail_bytes)} bytes")
        
        # Verify PNG format
        assert thumbnail_bytes.startswith(b'\x89PNG'), "Should be valid PNG"
        print(f"✓ Valid PNG format confirmed")
        
        # Save thumbnail
        save_thumbnail(chart_spec.id, thumbnail_bytes, "png")
        thumbnail_path = os.path.join(settings.THUMBNAILS_DIR, f"{chart_spec.id}.png")
        
        assert os.path.exists(thumbnail_path), "Thumbnail file should exist"
        print(f"✓ Thumbnail saved: {thumbnail_path}")
        
        # Update chart spec with thumbnail URI
        chart_spec.thumbnail_uri = f"/api/thumbnails/{chart_spec.id}.png"
        db.commit()
        
        
        print("\n=== Step 4: Analyze chart with GLM Vision ===")
        
        vision_provider = get_vision_provider()
        
        analysis_text = vision_provider.analyze_chart(
            image_path=thumbnail_path,
            spec=spec,
            prompt="Show a bar chart"
        )
        
        print(f"✓ GLM analysis completed")
        print(f"  Text length: {len(analysis_text)} chars")
        print(f"\n📊 Analysis Preview:")
        print(f"{analysis_text[:300]}...")
        
        # Save analysis to database
        analysis = Analysis(
            chart_spec_id=chart_spec.id,
            model_tag="glm-4v-flash",
            text=analysis_text
        )
        db.add(analysis)
        db.commit()
        
        print(f"\n✓ Analysis saved: {analysis.id}")
        
        
        print("\n" + "="*60)
        print("✅ FULL WORKFLOW TEST PASSED!")
        print("="*60)
        print(f"\nResults:")
        print(f"  Dataset ID: {dataset.id}")
        print(f"  Chart ID: {chart_spec.id}")
        print(f"  Analysis ID: {analysis.id}")
        print(f"  Thumbnail: {thumbnail_path} ({len(thumbnail_bytes)} bytes)")
        print(f"  Analysis: {len(analysis_text)} characters")
        
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        raise
        
    finally:
        # Cleanup
        print("\n=== Cleanup ===")
        
        db.query(Analysis).filter(Analysis.chart_spec_id == "test-chart-analysis").delete()
        db.query(ChartSpec).filter(ChartSpec.id == "test-chart-analysis").delete()
        db.query(Dataset).filter(Dataset.id == "test-dataset-analysis").delete()
        db.commit()
        
        # Remove files
        if os.path.exists("data/uploads/test-dataset-analysis.csv"):
            os.remove("data/uploads/test-dataset-analysis.csv")
            print("✓ Removed test CSV")
            
        thumbnail_path = os.path.join(settings.THUMBNAILS_DIR, "test-chart-analysis.png")
        if os.path.exists(thumbnail_path):
            os.remove(thumbnail_path)
            print("✓ Removed test thumbnail")
        
        db.close()


if __name__ == "__main__":
    test_full_analysis_workflow()
