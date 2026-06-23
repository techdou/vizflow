"""
Smoke tests for workflows API (Phase 5 - User Story 3)

T033: Smoke: PUT /workflows/{id} saves elements_json successfully
T034: Smoke: GET /workflows/{id} restores nodes/positions/edges
"""
import pytest
from fastapi.testclient import TestClient
from src.main import app


client = TestClient(app)


def test_t033_save_workflow_success():
    """
    T033: PUT /workflows/{id} saves elements_json successfully
    """
    workflow_id = "test-workflow-save"
    
    # Prepare workflow elements (React Flow format)
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
                "data": {"chart_spec_id": "chart-456", "vega_lite_spec": {}}
            }
        ],
        "edges": [
            {
                "id": "e-1-2",
                "source": "node-1",
                "target": "node-2"
            }
        ]
    }
    
    # Save workflow
    response = client.put(
        f"/api/workflows/{workflow_id}",
        json={"elements": elements}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == workflow_id
    assert "updated_at" in data
    print(f"✓ T033: Workflow saved with ID {workflow_id}")


def test_t034_load_workflow_restores_state():
    """
    T034: GET /workflows/{id} restores nodes/positions/edges
    """
    workflow_id = "test-workflow-load"
    
    # First, save a workflow
    elements = {
        "nodes": [
            {
                "id": "node-a",
                "type": "datasetNode",
                "position": {"x": 50, "y": 200},
                "data": {"dataset_id": "ds-abc", "name": "data.csv"}
            },
            {
                "id": "node-b",
                "type": "chartNode",
                "position": {"x": 350, "y": 200},
                "data": {
                    "chart_spec_id": "chart-xyz",
                    "vega_lite_spec": {"mark": "bar"}
                }
            },
            {
                "id": "node-c",
                "type": "analysisNode",
                "position": {"x": 650, "y": 200},
                "data": {"analysis_id": "analysis-123", "text": "Test analysis"}
            }
        ],
        "edges": [
            {"id": "e-a-b", "source": "node-a", "target": "node-b"},
            {"id": "e-b-c", "source": "node-b", "target": "node-c"}
        ]
    }
    
    save_response = client.put(
        f"/api/workflows/{workflow_id}",
        json={"elements": elements}
    )
    assert save_response.status_code == 200
    
    # Now load the workflow
    load_response = client.get(f"/api/workflows/{workflow_id}")
    assert load_response.status_code == 200
    
    data = load_response.json()
    assert data["id"] == workflow_id
    assert "elements" in data
    
    loaded_elements = data["elements"]
    assert len(loaded_elements["nodes"]) == 3
    assert len(loaded_elements["edges"]) == 2
    
    # Verify node positions are preserved
    node_a = next(n for n in loaded_elements["nodes"] if n["id"] == "node-a")
    assert node_a["position"]["x"] == 50
    assert node_a["position"]["y"] == 200
    
    # Verify edges are preserved
    edge_ids = [e["id"] for e in loaded_elements["edges"]]
    assert "e-a-b" in edge_ids
    assert "e-b-c" in edge_ids
    
    print(f"✓ T034: Workflow loaded with {len(loaded_elements['nodes'])} nodes and {len(loaded_elements['edges'])} edges")


def test_workflow_not_found():
    """
    Verify 404 when workflow doesn't exist
    """
    response = client.get("/api/workflows/nonexistent-id")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
    print("✓ Workflow 404 handling works")


def test_export_import_workflow():
    """
    Test export/import workflow cycle
    """
    workflow_id = "test-workflow-export"
    
    # Create and save workflow
    elements = {
        "nodes": [
            {
                "id": "export-node-1",
                "type": "datasetNode",
                "position": {"x": 100, "y": 100},
                "data": {"dataset_id": "ds-export", "name": "export.csv"}
            }
        ],
        "edges": []
    }
    
    client.put(
        f"/api/workflows/{workflow_id}",
        json={"elements": elements}
    )
    
    # Export workflow
    export_response = client.post(f"/api/workflows/export/{workflow_id}")
    assert export_response.status_code == 200
    
    export_data = export_response.json()
    assert export_data["version"] == "elements_v1"
    assert export_data["workflow"]["id"] == workflow_id
    assert "elements" in export_data
    
    print(f"✓ Export successful, version: {export_data['version']}")
    
    # Import workflow
    import_response = client.post(
        "/api/workflows/import",
        json=export_data
    )
    assert import_response.status_code == 200
    
    import_data = import_response.json()
    assert "id" in import_data
    assert import_data["id"] != workflow_id  # Should create new ID
    
    # Verify imported workflow can be loaded
    new_id = import_data["id"]
    load_response = client.get(f"/api/workflows/{new_id}")
    assert load_response.status_code == 200
    
    loaded = load_response.json()
    assert len(loaded["elements"]["nodes"]) == 1
    assert loaded["elements"]["nodes"][0]["id"] == "export-node-1"
    
    print(f"✓ Import successful, new ID: {new_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
