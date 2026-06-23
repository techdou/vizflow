"""
Manual smoke test for workflows API
Run with: python -m tests.smoke.manual_test_workflows
"""
from fastapi.testclient import TestClient
from src.main import app


def test_workflows():
    """Manual test for T033 and T034"""
    client = TestClient(app)
    
    print("\n=== Testing Workflows API ===\n")
    
    # T033: Save workflow
    print("T033: Testing PUT /workflows/{id}")
    workflow_id = "test-workflow-manual"
    
    elements = {
        "nodes": [
            {
                "id": "node-1",
                "type": "datasetNode",
                "position": {"x": 100, "y": 100},
                "data": {"dataset_id": "ds-123", "name": "test.csv"}
            },
            {
                "id": "node-2",
                "type": "chartNode",
                "position": {"x": 400, "y": 100},
                "data": {"chart_spec_id": "chart-456"}
            }
        ],
        "edges": [
            {"id": "e-1-2", "source": "node-1", "target": "node-2"}
        ]
    }
    
    response = client.put(
        f"/api/workflows/{workflow_id}",
        json={"elements": elements}
    )
    
    assert response.status_code == 200, f"Save failed: {response.text}"
    data = response.json()
    print(f"✓ Saved workflow: {data['id']}")
    print(f"  Updated at: {data['updated_at']}")
    
    # T034: Load workflow
    print("\nT034: Testing GET /workflows/{id}")
    response = client.get(f"/api/workflows/{workflow_id}")
    
    assert response.status_code == 200, f"Load failed: {response.text}"
    data = response.json()
    
    assert data["id"] == workflow_id
    assert len(data["elements"]["nodes"]) == 2
    assert len(data["elements"]["edges"]) == 1
    
    node1 = data["elements"]["nodes"][0]
    assert node1["position"]["x"] == 100
    assert node1["position"]["y"] == 100
    
    print(f"✓ Loaded workflow: {data['id']}")
    print(f"  Nodes: {len(data['elements']['nodes'])}")
    print(f"  Edges: {len(data['elements']['edges'])}")
    print(f"  Node 1 position: ({node1['position']['x']}, {node1['position']['y']})")
    
    # Test export
    print("\nTesting export workflow")
    response = client.post(f"/api/workflows/export/{workflow_id}")
    
    assert response.status_code == 200, f"Export failed: {response.text}"
    export_data = response.json()
    
    assert export_data["version"] == "elements_v1"
    assert export_data["workflow"]["id"] == workflow_id
    print(f"✓ Exported workflow version: {export_data['version']}")
    
    # Test import
    print("\nTesting import workflow")
    response = client.post(
        "/api/workflows/import",
        json=export_data
    )
    
    assert response.status_code == 200, f"Import failed: {response.text}"
    import_data = response.json()
    
    new_id = import_data["id"]
    assert new_id != workflow_id  # Should create new ID
    print(f"✓ Imported as new workflow: {new_id}")
    
    # Verify imported workflow
    response = client.get(f"/api/workflows/{new_id}")
    assert response.status_code == 200
    loaded = response.json()
    assert len(loaded["elements"]["nodes"]) == 2
    print(f"✓ Verified imported workflow has {len(loaded['elements']['nodes'])} nodes")
    
    # Test 404
    print("\nTesting 404 for nonexistent workflow")
    response = client.get("/api/workflows/nonexistent-id")
    assert response.status_code == 404
    print("✓ 404 handling works correctly")
    
    print("\n=== All workflow tests passed! ===\n")


if __name__ == "__main__":
    test_workflows()
