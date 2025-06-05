from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from weaviate import Client
from threading import Event
import threading
import uvicorn
import webbrowser
import logging
from rm_operations import RMOperations
from models import Config, RemovePointsRequest
from middleware import setup_middleware
from static_files import setup_static_files
from config import load_config
from weaviate_recordmanager_utils.weaviate_client_singleton import get_weaviate_client
from server import Server
from typing import List, Optional
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

config = load_config()
app = FastAPI()

setup_middleware(app)
setup_static_files(app, config['static_directory'], config['index_html_path'], config['browser2_html_path'])

RM = RMOperations(docs_index_name=config['WEAVIATE_DOCS_INDEX_NAME'])

# Mock last modified time
last_modified_time = datetime.now(timezone.utc)

@app.get("/data/last_modified")
async def get_last_modified():
    return {"last_modified": last_modified_time.isoformat() + 'Z'}

@app.get("/config", response_model=Config)
async def get_config():
    return Config(port=config['CLUSTER_BACKEND_PORT'])

@app.get("/plotV1/show_all_plot_data", response_class=JSONResponse)
async def show_all_plot_data(client: Client = Depends(get_weaviate_client)):
    try:
        RM.set_all_ids_visible(client)
        return JSONResponse(content={"message": "All points are now shown on plot"})
    except Exception as e:
        logger.error(f"Error resetting plot point: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post("/plotV1/remove_points", response_class=JSONResponse)
async def remove_points(request: RemovePointsRequest, client: Client = Depends(get_weaviate_client)):
    try:
        selected_ids = request.selected_ids
        RM.set_ids_to_nonvisible(client, selected_ids)
        return JSONResponse(content={"message": "Selected points removed successfully"})
    except Exception as e:
        logger.error(f"Error removing selected embeddings: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)
    
@app.post("/plotV1/add_back_points", response_class=JSONResponse)
async def remove_points(request: RemovePointsRequest, client: Client = Depends(get_weaviate_client)):
    try:
        selected_ids = request.selected_ids
        RM.set_ids_to_visible(client, selected_ids)
        return JSONResponse(content={"message": "Selected points add back to successfully"})
    except Exception as e:
        logger.error(f"Error adding selected embeddings: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

returned_fields_default = ['clusterID', 'tsne_x', 'tsne_y', 'page_content', 'filename']
@app.get("/plotV1/{plot_type}/{selection}", response_class=JSONResponse)
async def get_scatter_plot_data(
    plot_type: str,
    selection: str,
    client: Client = Depends(get_weaviate_client),
    fields: Optional[List[str]] = Query(None, description="List of fields to return")
):
    
#### curl -G "http://localhost:8025/plotV1/scatter_plot/nonvisible" --data-urlencode "fields=id" --data-urlencode "fields=filename" --data-urlencode "fields=page_content"

    if selection == 'visible':
        plot_code = 1
    elif selection == 'nonvisible':
        plot_code = 0
    else:
        return JSONResponse(content={"error": f"{selection} in endpoint '/data/{plot_type}/{selection}' is not valid."}, status_code=400)

    data_methods = ['scatter_plot', 'bar_plot', 'centroid_plot']
    if plot_type not in data_methods:
        return JSONResponse(content={"error": "Plot type not found"}, status_code=404)

    # Use provided fields or default to returned_fields_default
    returned_fields = fields if fields else returned_fields_default

    logger.info(f"Fields to be returned: {returned_fields}")

    try:
        data = RM.get_filtered_by_plot_code(client, plot_code, returned_fields)
        result = []
        for pd in data:
            item = {field: pd[field] for field in returned_fields if field in pd}
            item['id'] = pd['id']  # Ensure 'id' is always included
            result.append(item)

        # Sort the result by cluster number if 'clusterID' is in the fields
        if 'clusterID' in returned_fields:
            result = sorted(result, key=lambda x: x['clusterID'])

        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return JSONResponse(content={"error": str(e)}, status_code=500)
@app.post("/data/operations/{operation}", response_class=JSONResponse)
async def perform_data_operation(operation: str, client: Client = Depends(get_weaviate_client)):
    try:
        
        result = "WOP"

        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/data/retrieve/field_names", response_class=JSONResponse)
async def get_field_names(client: Client = Depends(get_weaviate_client)):
    try:
        field_names = RM.get_all_field_names(client)
        return JSONResponse(content=field_names)
    except Exception as e:
        logger.error(f"Error retrieving field names: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

if __name__ == "__main__":
    server = Server()
    server.run(app = app, port = config['CLUSTER_BACKEND_PORT'])
    webbrowser.open(f"http://localhost:{config['CLUSTER_BACKEND_PORT']}/")
    webbrowser.open(f"http://localhost:{config['CLUSTER_BACKEND_PORT']}/browser2")
    try:
        while not server.stop_event.is_set():
            server.stop_event.wait(1)
    except KeyboardInterrupt:
        print('Shutting down server...')
        server.stop()
        print('Server shut down successfully.')
