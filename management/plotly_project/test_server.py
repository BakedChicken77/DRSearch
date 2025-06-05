# test_api.py

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Import the app from the main script
from app_weaviatev4 import app

client = TestClient(app)

# Mock dependencies that are not provided
# This is necessary because RMOperations and other dependencies are not defined
# You should replace these mocks with actual implementations if available

# Mock for RMOperations
class MockRMOperations:
    def __init__(self, *args, **kwargs):
        pass

    def close_client(self):
        pass

    def set_all_ids_visible(self):
        pass

    def set_ids_to_nonvisible(self, selected_ids):
        pass

    def set_ids_to_visible(self, selected_ids):
        pass

    def set_ids_no_rag(self, selected_ids):
        pass

    def set_ids_yes_rag(self, selected_ids):
        pass

    def get_filtered_by_plot_code(self, plot_code, returned_fields):
        return [
            {'uuid': 'uuid1', 'filename': 'file1', 'clusterID': 0},
            {'uuid': 'uuid2', 'filename': 'file2', 'clusterID': 1},
        ]

    def get_all_field_names(self):
        return ['uuid', 'filename', 'page_content']

    def get_collection_names(self):
        return {'collection1': {}, 'collection2': {}}

    def set_ALL_ids_yes_rag(self):
        pass

    def get_collection_schema(self):
        return {'schema': 'some_schema'}

    def get_filtered_data(self, field_name, value, fields):
        return [{'uuid': 'uuid1', field_name: value}]

    def set_all_values_per_filename(self, filename, field, value):
        pass

    def reset_plot_field_values(self, field, default_value):
        pass

    def get_field_values(self, fields):
        return [
            {'uuid': 'uuid1', 'vector': [0.1, 0.2], 'filename': 'file1', 'page_content': 'content1'},
            {'uuid': 'uuid2', 'vector': [0.3, 0.4], 'filename': 'file2', 'page_content': 'content2'},
        ]

    def add_new_field(self, field, field_type, default_value):
        pass

    def _check_valid_fields(self, fields):
        return fields, []

# Mock the get_rm_operations dependency
@pytest.fixture(autouse=True)
def mock_rm_operations():
    with patch('app_weaviatev4.get_rm_operations', return_value=MockRMOperations()):
        yield

# Mock for config
@pytest.fixture(autouse=True)
def mock_config():
    with patch('app_weaviatev4.config', {
        'CLUSTER_BACKEND_PORT': 8000,
        'plot_configs': {
            'scatter_plot': ['uuid', 'filename', 'clusterID'],
        },
        'supported_plot_types': ['scatter_plot'],
        'WEAVIATE_DOCS_INDEX_NAME': 'default_collection',
        'static_directory': './static',
        'max_clusters': 5,
        'min_clusters': 2,
        'TEXT_KEY': 'page_content',
        'weaviateUi_settings': {'1': 'setting1', '2': 'setting2', '3': 'setting3'},
        'reference_directory': './documents',
        'browser2_html': 'browser2.html',
        'weaviateui_html': 'weaviateui.html',
        'browser3_html': 'browser3.html',
    }):
        yield

# Tests for /data/last_modified endpoint
class TestDataLastModified:
    def test_get_last_modified(self):
        response = client.get("/data/last_modified")
        assert response.status_code == 200
        json_response = response.json()
        assert "last_modified" in json_response

# Tests for /config endpoint
class TestConfig:
    def test_get_config(self):
        response = client.get("/config")
        assert response.status_code == 200
        json_response = response.json()
        assert "port" in json_response

# Tests for /plotV1 endpoints
class TestPlotV1:
    def test_show_all_plot_data(self):
        response = client.get("/plotV1/show_all_plot_data")
        assert response.status_code == 200
        json_response = response.json()
        assert json_response == {"message": "All points are now shown on plot"}

    def test_remove_points_valid(self):
        data = {
            "selected_ids": ["uuid1", "uuid2"]
        }
        response = client.post("/plotV1/remove_points", json=data)
        assert response.status_code == 200
        json_response = response.json()
        assert json_response == {"message": "Selected points removed successfully"}

    def test_remove_points_missing_selected_ids(self):
        data = {}
        response = client.post("/plotV1/remove_points", json=data)
        assert response.status_code == 422  # Unprocessable Entity due to validation error

    def test_add_back_points_valid(self):
        data = {
            "selected_ids": ["uuid1", "uuid2"]
        }
        response = client.post("/plotV1/add_back_points", json=data)
        assert response.status_code == 200
        json_response = response.json()
        assert json_response == {"message": "Selected points add back to successfully"}

    def test_remove_from_rag_valid(self):
        data = {
            "selected_ids": ["uuid1", "uuid2"]
        }
        response = client.post("/plotV1/remove_from_rag", json=data)
        assert response.status_code == 200
        json_response = response.json()
        assert json_response == {"message": "Selected points removed from RAG Search successfully"}

    def test_add_to_rag_valid(self):
        data = {
            "selected_ids": ["uuid1", "uuid2"]
        }
        response = client.post("/plotV1/add_to_rag", json=data)
        assert response.status_code == 200
        json_response = response.json()
        assert json_response == {"message": "Selected points added to RAG Search successfully"}

    def test_get_plot_data_valid(self):
        response = client.get("/plotV1/scatter_plot/visible")
        assert response.status_code == 200
        json_response = response.json()
        assert isinstance(json_response, list)
        assert all('uuid' in item for item in json_response)

    def test_get_plot_data_invalid_selection(self):
        response = client.get("/plotV1/scatter_plot/invalid_selection")
        assert response.status_code == 500  # Due to status_code=0 in the code

    def test_get_plot_data_invalid_plot_type(self):
        response = client.get("/plotV1/invalid_plot_type/visible")
        assert response.status_code == 404  # Plot type not found

# Tests for /data/operations endpoint
class TestDataOperations:
    def test_data_operations_recalc_clusters(self):
        data = {
            "max_clusters": 5,
            "min_clusters": 2
        }
        response = client.post("/data/operations/recalc_clusters", json=data)
        assert response.status_code == 200
        json_response = response.json()
        assert "status" in json_response

    def test_data_operations_invalid_operation(self):
        data = {}
        response = client.post("/data/operations/invalid_operation", json=data)
        assert response.status_code == 500

# Tests for /data/retrieve/field_names endpoint
class TestDataRetrieve:
    def test_get_field_names(self):
        response = client.get("/data/retrieve/field_names")
        assert response.status_code == 200
        json_response = response.json()
        assert isinstance(json_response, list)
        assert 'uuid' in json_response

# Tests for /data/schema endpoints
class TestDataSchema:
    def test_get_all_collection_names(self):
        response = client.get("/data/schema/get_all_collection_names")
        assert response.status_code == 200
        json_response = response.json()
        assert "result" in json_response
        assert isinstance(json_response["result"], list)

    def test_set_selected_collection_valid(self):
        data = {"collection_name": "collection1"}
        response = client.post("/data/schema/set_selected_collection", json=data)
        assert response.status_code == 200
        json_response = response.json()
        assert json_response["status"] == "success"

    def test_set_selected_collection_missing_collection_name(self):
        data = {}
        response = client.post("/data/schema/set_selected_collection", json=data)
        assert response.status_code == 400
        json_response = response.json()
        assert json_response["status"] == "error"

    def test_get_selected_collection(self):
        response = client.get("/data/schema/get_selected_collection")
        assert response.status_code == 200
        json_response = response.json()
        assert "selected_collection" in json_response

# Tests for /data/{buttontype} endpoint
class TestWeaviateUIOperation:
    def test_weaviateUI_operation_get_filtered_data(self):
        data = {
            "setting1": "field_name",
            "setting2": "value",
            "setting3": "fields"
        }
        response = client.post("/data/get_filtered_data", json=data)
        assert response.status_code == 200
        json_response = response.json()
        assert "result" in json_response

    def test_weaviateUI_operation_invalid_buttontype(self):
        data = {}
        response = client.post("/data/invalid_buttontype", json=data)
        assert response.status_code == 500

# Tests for /documents/pdf endpoint
class TestDocumentsPDF:
    def test_get_pdf_valid(self):
        with patch('pathlib.Path.exists', return_value=True):
            response = client.get("/documents/pdf/test.pdf")
            assert response.status_code == 200
            assert response.headers["content-type"] == "application/pdf"

    def test_get_pdf_invalid(self):
        with patch('pathlib.Path.exists', return_value=False):
            response = client.get("/documents/pdf/nonexistent.pdf")
            assert response.status_code == 500
            json_response = response.json()
            assert "error" in json_response

# Tests for /check_database_init_status endpoint
class TestDatabaseInitStatus:
    def test_check_database_init_status(self):
        response = client.get("/check_database_init_status")
        assert response.status_code == 200
        json_response = response.json()
        assert "status" in json_response

# Tests for /initialize_database endpoint
class TestInitializeDatabase:
    def test_initialize_database(self):
        response = client.get("/initialize_database")
        assert response.status_code == 200
        json_response = response.json()
        assert "status" in json_response
