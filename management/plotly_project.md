```python
# plotly_project\app.py

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

```

```python
# plotly_project\app_weaviatev4.py

from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, FileResponse
from contextlib import asynccontextmanager
from threading import Event
import threading
import uvicorn
import webbrowser
import logging
from rm_operations import RMOperations
from models import Config, RemovePointsRequest, Settings
from middleware import setup_middleware
from static_files import setup_static_files
from config import load_config
from server import Server
from typing import List, Optional
from datetime import datetime, timezone
import json
import numpy as np
from clustering_utils2 import determine_optimal_clusters
from sklearn.cluster import KMeans
from sklearn.manifold import TSNE
from Clustering_and_Delete_Weaviate_Embeddings2 import calc_tsne_and_clusters

logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# logging.getLogger("httpx").setLevel(logging.WARNING)  # Set httpx logging to WARNING level. Otherwise, all write and reads to Weaviate are logged
logger = logging.getLogger(__name__)

config = load_config()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks here
    yield
    # Shutdown tasks here

    closer = get_rm_operations()
    closer.close_client()

def get_rm_operations() -> RMOperations:
    # Read the selected collection name from the JSON file
    try:
        with open('selected_collection.json', 'r') as f:
            selected_config = json.load(f)
            selected_collection_name = selected_config.get('WEAVIATE_DOCS_INDEX_NAME', config['WEAVIATE_DOCS_INDEX_NAME'])
    except FileNotFoundError:
        selected_collection_name = config['WEAVIATE_DOCS_INDEX_NAME']
    except Exception as e:
        logger.error(f"Error reading selected collection: {e}")
        selected_collection_name = config['WEAVIATE_DOCS_INDEX_NAME']

    return RMOperations(docs_index_name=selected_collection_name)

app = FastAPI(lifespan=lifespan)

setup_middleware(app)
setup_static_files(
    app, 
    config['static_directory'], 
)


# Mock last modified time
last_modified_time = datetime.now(timezone.utc)

#### curl -X GET "http://localhost:8025/data/last_modified" -H "Accept: application/json"
@app.get("/data/last_modified")
async def get_last_modified(RM: RMOperations = Depends(get_rm_operations)):
    # return {"last_modified": last_modified_time.isoformat() + 'Z'}
    last_modified = RM.get_last_update()


    return {"last_modified": f"{last_modified}"}

@app.get("/config", response_model=Config)
async def get_config():
    return Config(port=config['CLUSTER_BACKEND_PORT'])


#### curl -X GET "http://localhost:8025/plotV1/show_all_plot_data" -H "Accept: application/json" 
@app.get("/plotV1/show_all_plot_data", response_class=JSONResponse)
async def show_all_plot_data(RM: RMOperations = Depends(get_rm_operations)):
    try:
        RM.set_all_ids_visible()
        return JSONResponse(content={"message": "All points are now shown on plot"})
    except Exception as e:
        logger.error(f"Error resetting plot point: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

##### curl -X POST "http://localhost:8025/plotV1/remove_points" -H "Content-Type: application/json" -d "{\"selected_ids\": [\"87d8e09c-e155-5cb1-9b47-bad70ae8bf2c\", \"a4b1c2d3-e4f5-6789-0abc-def123456789\"]}"

@app.post("/plotV1/remove_points", response_class=JSONResponse)
async def remove_points(request: RemovePointsRequest, RM: RMOperations = Depends(get_rm_operations)):
    try:
        # Directly access the parsed Pydantic model's data
        logger.info(f"Request body: {request}")

        selected_ids = request.selected_ids  # Access the selected_ids field directly from the model
        logger.info(f"selected_ids: {selected_ids}")

        RM.set_ids_to_nonvisible(selected_ids)
        return JSONResponse(content={"message": "Selected points removed successfully"})
    except Exception as e:
        logger.error(f"Error removing selected embeddings: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)
    
@app.post("/plotV1/add_back_points", response_class=JSONResponse)
async def add_back_points(request: RemovePointsRequest, RM: RMOperations = Depends(get_rm_operations)):
    try:
        selected_ids = request.selected_ids
        RM.set_ids_to_visible(selected_ids)
        return JSONResponse(content={"message": "Selected points add back to successfully"})
    except Exception as e:
        logger.error(f"Error adding selected embeddings: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)
    

@app.post("/plotV1/remove_from_rag", response_class=JSONResponse)
async def remove_from_RAG(request: RemovePointsRequest, RM: RMOperations = Depends(get_rm_operations)):
    try:
        selected_ids = request.selected_ids
        RM.set_ids_no_rag(selected_ids)
        return JSONResponse(content={"message": "Selected points removed from RAG Search successfully"})
    except Exception as e:
        logger.error(f"Error removing selected embeddings from RAG Search: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post("/plotV1/add_to_rag", response_class=JSONResponse)
async def add_to_RAG(request: RemovePointsRequest, RM: RMOperations = Depends(get_rm_operations)):
    try:
        selected_ids = request.selected_ids
        RM.set_ids_yes_rag(selected_ids)
        return JSONResponse(content={"message": "Selected points added to RAG Search successfully"})
    except Exception as e:
        logger.error(f"Error adding selected embeddings to RAG Search: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/plotV1/{plot_type}/{selection}", response_class=JSONResponse)
async def get_plot_data(
    plot_type: str,
    selection: str,
    fields: Optional[List[str]] = Query(None, description="List of fields to return"),
    RM: RMOperations = Depends(get_rm_operations)
):


#### curl -G "http://localhost:8025/plotV1/scatter_plot/nonvisible" --data-urlencode "fields=uuid" --data-urlencode "fields=filename" --data-urlencode "fields=page_content"

    if selection == 'visible':
        plot_code = 1
    elif selection == 'nonvisible':
        plot_code = 0
    else:
        return JSONResponse(content={"error": f"{selection} in endpoint '/data/{plot_type}/{selection}' is not valid."}, status_code=0)

    plot_configs = config['plot_configs']
    returned_fields = plot_configs[plot_type]
    if not returned_fields:
        return JSONResponse(content={"error":f"{plot_type} is not a valid 'selection"}, status_code=500)
   
    if plot_type == "scatter_plot":
        if plot_type not in config['supported_plot_types']:
            return JSONResponse(content={"error": "Plot type not found"}, status_code=404)

        try:
            data = RM.get_filtered_by_plot_code(plot_code, returned_fields)

            if not data:
                logger.error(f"Info: No {selection} points returned from the database")
                return JSONResponse(content={"Info": f"Error: No {selection} points returned from the database"}, status_code=500)

            result = []
            for pd in data:
                item = {field: pd[field] for field in returned_fields if field in pd}
                item['uuid'] = pd['uuid']  # Ensure 'uuid' is always included
                result.append(item)

            # Sort the result by cluster number if 'clusterID' is in the fields
            if 'clusterID' in returned_fields:
                result = sorted(result, key=lambda x: x['clusterID'])

            return JSONResponse(content=result)
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            return JSONResponse(content={"error": str(e)}, status_code=500)
        
@app.post("/data/operations/{operation}", response_class=JSONResponse)
async def perform_data_operation(
    operation: str,
    request: Request,
    RM: RMOperations = Depends(get_rm_operations)
):
    try:
        if operation == 'recalc_clusters':
            data = await request.json()
            max_clusters = data.get("max_clusters")
            min_clusters = data.get("min_clusters")
            index = get_selected_collection_name()
            response = calc_tsne_and_clusters(index, max_clusters, min_clusters, recalc_tsne_clusters_only=True)

            return JSONResponse(content={"status": response})
        
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

#### curl -G "http://localhost:8025/data/retrieve/field_names" --data-urlencode "fields=uuid"
@app.get("/data/retrieve/field_names", response_class=JSONResponse)
async def get_field_names(RM: RMOperations = Depends(get_rm_operations)):
    try:
        field_names = RM.get_all_field_names()
        return JSONResponse(content=field_names)
    except Exception as e:
        logger.error(f"Error retrieving field names: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)
    
#### curl -G "http://localhost:8025/data/schema/get_all_collection_names"
@app.get("/data/schema/get_all_collection_names", response_class=JSONResponse)
async def get_all_collection_names(
    RM: RMOperations = Depends(get_rm_operations)
):
    try:
        names = RM.get_collection_names()
        return JSONResponse(content={"result": list(names.keys())})
    except Exception as e:
        return JSONResponse(content={"result": f"Failed to get collection names: {e}"})            

#### curl -G "http://localhost:8025/data/schema/get_all_collection_names"
def get_selected_collection_name():
    try:
        with open('selected_collection.json', 'r') as f:
            selected_config = json.load(f)
            selected_collection_name = selected_config.get('WEAVIATE_DOCS_INDEX_NAME', config['WEAVIATE_DOCS_INDEX_NAME'])
    except FileNotFoundError:
        selected_collection_name = config['WEAVIATE_DOCS_INDEX_NAME']
    except Exception as e:
        logger.error(f"Error reading selected collection: {e}")
        selected_collection_name = config['WEAVIATE_DOCS_INDEX_NAME']
    return selected_collection_name

#### curl -X POST "http://localhost:8025/data/schema/set_selected_collection" -H "Content-Type: application/json" -d "{\"collection_name\": \"SEPs_F_T_C_W_A_V_Summaries\"}"
@app.post("/data/schema/set_selected_collection")
async def set_selected_collection(request: Request):
    data = await request.json()
    collection_name = data.get('collection_name')
    if collection_name:
        # Persist the selected collection name to a JSON file
        with open('selected_collection.json', 'w') as f:
            json.dump({'WEAVIATE_DOCS_INDEX_NAME': collection_name}, f)
        
        # # Optionally, update the config in memory
        # config['WEAVIATE_DOCS_INDEX_NAME'] = collection_name

        # Reinitialize RMOperations with the new collection name
        RM = RMOperations(docs_index_name=collection_name)
        
        return {"status": "success", "message": f"Selected collection set to {collection_name}"}
    else:
        return JSONResponse(content={"status": "error", "message": "Collection name not provided"}, status_code=400)

@app.get("/data/schema/get_selected_collection")
async def get_selected_collection():
    try:
        with open('selected_collection.json', 'r') as f:
            selected_config = json.load(f)
            selected_collection_name = selected_config.get('WEAVIATE_DOCS_INDEX_NAME', config['WEAVIATE_DOCS_INDEX_NAME'])
        return {"selected_collection": selected_collection_name}
    except FileNotFoundError:
        return {"selected_collection": config['WEAVIATE_DOCS_INDEX_NAME']}
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
    
#### curl -X GET "http://localhost:8025/data/set_field_values_by_id" -H "Content-Type: application/json" -d "{\"setting1\": \"value1\", \"setting2\": \"value2\", \"setting3\": \"value3\", \"setting4\": \"value4\", \"setting5\": \"value5\"}"
@app.post("/data/{buttontype}", response_class=JSONResponse)
async def weaviateUI_operation(
    buttontype: str,
    settings: Settings,
    fields: Optional[List[str]] = Query(None, description="List of fields to return"),
    RM: RMOperations = Depends(get_rm_operations)
):
    # Extract the settings
    settings_data = {k: v for k, v in settings.model_dump().items() if v is not None}   

    config_button_settings = config['weaviateUi_settings']

    config_settings = {}
    # Loop through config_settings to update values based on settings_data
    for i in range(1, len(config_button_settings) + 1):
        key = config_button_settings.get(str(i))
        if key and key in settings_data:
            # Assign the value from settings_data to a new key in config_settings
            config_settings[key] = settings_data[key]

    button_list = [
        'set_all_values_per_filename', 
        'set_field_values_by_id', 
        'add_all_to_rag', 
        'set_ids_to_nonvisible', 
        'get_filtered_data', 
        'get_collection_schema',
        'force_initialize_fields',
        'get_all_collection_names'
    ]

    if buttontype in button_list:
        if buttontype == 'get_filtered_data':
            logger.info(f"""\
buttontype: {buttontype}
field_name: {config_settings['setting1']}
value: {config_settings['setting2']}
fields: {config_settings['setting3']}
""")
            result = RM.get_filtered_data(
                field_name=config_settings['setting1'],
                value=config_settings['setting2'],
                fields=[config_settings['setting3']]
            )
            
            return JSONResponse(content={"result": result})
        elif buttontype == 'force_initialize_fields':
            max_clusters = config["max_clusters"]
            min_clusters = config["min_clusters"]
            index = config['WEAVIATE_DOCS_INDEX_NAME']
            response = calc_tsne_and_clusters(index, max_clusters,min_clusters, force_reinitialize=True)
            return JSONResponse(content={"result": response})

        elif buttontype == 'get_collection_schema':###The button name doesn't match the function it performs. I added this as a quick test to get the schema
        ## This button returns the schema
            try:
                schema = RM.get_collection_schema()
                return JSONResponse(content={"result": schema})
            except Exception as e:
                return JSONResponse(content={"result": f"Failed to get schema: {e}"})
            
        elif buttontype == 'get_all_collection_names':
        ## This button returns the names for all collections in Weaviate
            try:
                names = RM.get_collection_names()
                return JSONResponse(content={"result": list(names.keys())})
            except Exception as e:
                return JSONResponse(content={"result": f"Failed to get collection names: {e}"})            
            
        elif buttontype == 'add_all_to_rag':
            try:
                RM.set_ALL_ids_yes_rag()
                return JSONResponse(content={"message": "Successfully: All vectors are now included in RAG Search"})
            except Exception as e:
                logger.error(f"Error adding all embeddings back to RAG Search: {e}")
                return JSONResponse(content={"error": str(e)}, status_code=500)

        elif buttontype == 'set_all_values_per_filename':###The button name doesn't match the function it performs. I added this as a quick test to get the schema
            try:
                filename=config_settings['setting1'],
                field=config_settings['setting2'],
                value=config_settings['setting3'],                
                RM.set_all_values_per_filename(
                    filename=filename,
                    field=field,
                    value=value,
                )
                return JSONResponse(content={"message": f"Successfully set all values for {field} to {value} for filename {filename}"})
            except Exception as e:
                logger.error(f"Error setting all values for {field} in {filename} to {value}: {e}")
                return JSONResponse(content={"error": str(e)}, status_code=500)

        else:
            return JSONResponse(content={"error": str(e)}, status_code=500)

    return JSONResponse(content={"error": f"{buttontype} is not a valid button"}, status_code=500)

#### curl -X GET "http://localhost:8025/documents/pdf/test.pdf" -H "Content-Type: application/json"
@app.get("/documents/pdf/{pdf_name}", response_class=FileResponse)
async def get_pdf(pdf_name: str):
    pdf_path = config['reference_directory'] / pdf_name # Update this to the correct path

    if not pdf_path.exists():
        return JSONResponse(content={"error": f"{pdf_name} does not exist"}, status_code=500)
    
    return FileResponse(pdf_path, media_type='application/pdf', filename=pdf_name)



#### curl -X GET "http://localhost:8025/check_database_init_status" -H "Content-Type: application/json"
@app.get("/check_database_init_status", response_class=JSONResponse)
async def check_database_init_status(
    RM: RMOperations = Depends(get_rm_operations)
):

        prunning_fields_types = {
            'use4RAG': ('boolean',True),
            'clusterID': ('int', -1),#'-1' indicated 'no cluster assigned
            'tsne_x': ('number', 0),
            'tsne_y': ('number', 0),
            'plot_code': ('int', 1),
            # 'signature': ('string', 'True')
            # 'plot_params_last_modified': ('date', )#formatted as RFC3339
        }
        prun_fields = list(prunning_fields_types.keys())
        check_field, _ = RM._check_valid_fields(prun_fields)
        field_to_add = [key for key in prunning_fields_types.keys() if key not in check_field]

        if not field_to_add:
            return JSONResponse(content={"status": "OK"})
        else:
            return JSONResponse(content={"status": "Not Initialized"})


#### curl -X GET "http://localhost:8025/initialize_database" -H "Content-Type: application/json"
@app.get("/initialize_database", response_class=JSONResponse)
async def calculate_clusters():
    try:
        max_clusters = config["max_clusters"]
        min_clusters = config["min_clusters"]
        index = get_selected_collection_name()
        response = calc_tsne_and_clusters(index, max_clusters, min_clusters)

        return JSONResponse(content={"status": response})

    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

async def calculate_tsne_and_clusters(
    max_clusters=None,
    min_clusters=None,
    RM: RMOperations = Depends(get_rm_operations)
):
        if not max_clusters:
            max_clusters = config['max_clusters']
        if not min_clusters:
            min_clusters = config['min_clusters']


        prunning_fields_types = {
            'use4RAG': ('boolean',True),
            'clusterID': ('int', -1),#'-1' indicated 'no cluster assigned
            'tsne_x': ('number', 0),
            'tsne_y': ('number', 0),
            'plot_code': ('int', 1),
            # 'signature': ('string', 'True')
            # 'plot_params_last_modified': ('date', )#formatted as RFC3339
        }
        prun_fields = list(prunning_fields_types.keys())

        check_field, _ = RM._check_valid_fields(prun_fields)
        field_to_add = [key for key in prunning_fields_types.keys() if key not in check_field]
        if field_to_add:        
            for field in field_to_add:
                field_type = prunning_fields_types[field][0]
                default_value = prunning_fields_types[field][1]
                RM.add_new_field(field, field_type, default_value)#'-1' indicated 'no cluster assigned

        if check_field:
            if not isinstance(check_field,list):
                check_field = [check_field]

            for field in check_field:
                default_value = prunning_fields_types[field][1]
                RM.reset_plot_field_values(field,default_value)

        TEXT_KEY = config['TEXT_KEY'] # the key for the text used to create each embedding. TEXT_KEY = page_content
        fields_for_Calc = ['vector', 'filename', TEXT_KEY, 'uuid'] 
        all_data = RM.get_field_values(fields_for_Calc)

        # Extract embeddings, texts, metadata, and IDs from the results
        embeddings = [item.get("vector", {}) for item in all_data]
        texts = [item.get(TEXT_KEY, {}) for item in all_data]
        filenames = [item.get("filename", {}) for item in all_data]
        uuid = [item["uuid"] for item in all_data]

        # Convert embeddings to numpy array for clustering
        embedding_array = np.array(embeddings)

        # num_clusters = optimal_cluster_count(embedding_array, max_clusters=num_clusters)
        
        greater_than_length_message = f"""
'max_clusters' is set to {max_clusters}. 'all_Data' contains {len(all_data)} samples. \
'max_clusters' must be set to a value between {min_clusters} and n_samples - 1 ({len(all_data)-1}). \
Setting 'max_clusters' to maximum value (max_clusters = {len(all_data)-1}).
"""
        less_than_two_message = f"""
'max_clusters' is set to {max_clusters}. \
'max_clusters' must be set to a value between {min_clusters} and n_samples - 1 ({len(all_data)-1}). \
Setting 'max_clusters' to minimum value of {min_clusters}.
"""     

        if max_clusters >= len(all_data):
            print(greater_than_length_message)
            max_clusters = len(all_data)-1
        elif max_clusters < min_clusters:
            print(less_than_two_message)
            max_clusters = min_clusters

        try:
            num_clusters = await determine_optimal_clusters(embedding_array,max_clusters=max_clusters,min_clusters=min_clusters, use_gpu=False)
            print(f'Optimal number of clusters: {num_clusters}')

            # Apply k-means clustering
            kmeans = KMeans(n_clusters=num_clusters, random_state=0).fit(embedding_array)
            # Get cluster labels
            labels = kmeans.labels_


            # Automatically determine perplexity
            perplexity = min(50, max(5, int(np.sqrt(len(embedding_array)))))    

            # Relationship visualization using t-SNE
            tsne = TSNE(n_components=2, random_state=0,perplexity=perplexity)
            tsne_results = tsne.fit_transform(embedding_array)

            tsne_x = []
            tsne_y = []
            for x0,y0 in tsne_results:
                tsne_x.append(float(x0))
                tsne_y.append(float(y0))

            clusterID = labels.astype(int).tolist()

            return uuid, clusterID, tsne_x, tsne_y
        
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            return JSONResponse(content={"error": str(e)}, status_code=500)


if __name__ == "__main__":
    server = Server()
    server.run(app = app, port = config['CLUSTER_BACKEND_PORT'])
    webbrowser.open(f"http://localhost:{config['CLUSTER_BACKEND_PORT']}/")
    webbrowser.open(f"http://localhost:{config['CLUSTER_BACKEND_PORT']}/{config['browser2_html']}")
    webbrowser.open(f"http://localhost:{config['CLUSTER_BACKEND_PORT']}/{config['weaviateui_html']}")
    webbrowser.open(f"http://localhost:{config['CLUSTER_BACKEND_PORT']}/{config['browser3_html']}")    
    try:
        while not server.stop_event.is_set():
            server.stop_event.wait(1)
    except KeyboardInterrupt:
        print('Shutting down server...')
        server.stop()
        print('Server shut down successfully.')

```

```python
# plotly_project\CLASS_Clustering_and_Delete_Weaviate_Embeddings.py

import os
from contextlib import contextmanager
import numpy as np
import weaviate
import pandas as pd
from dotenv import load_dotenv
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity
import plotly.express as px
from langchain.indexes import SQLRecordManager
from Excel_Formating import apply_excel_formatting
from generate_plot import plot_cluster

class VectorStorePruner:
    def __init__(self, weaviate_url, weaviate_api_key, docs_index_name, record_manager_db_url, num_clusters=35, text_key='page_content'):
        self.weaviate_url = weaviate_url
        self.weaviate_api_key = weaviate_api_key
        self.docs_index_name = docs_index_name
        self.record_manager_db_url = record_manager_db_url
        self.num_clusters = num_clusters
        self.text_key = text_key
        self.data = []
        self.embeddings = []
        self.texts = []
        self.filenames = []
        self.ids = []
        self.other_fields = {}
        self.labels = []
        self.embedding_array = None
        load_dotenv()

    @contextmanager
    def weaviate_client(self):
        client = weaviate.Client(
            url=self.weaviate_url,
            auth_client_secret=weaviate.AuthApiKey(api_key=self.weaviate_api_key),
        )
        try:
            yield client
        finally:
            client._connection.close()

    def fetch_data(self):
        with self.weaviate_client() as client:
            schema = client.schema.get()
            class_schema = next((cls for cls in schema['classes'] if cls['class'] == self.docs_index_name), None)

            if not class_schema:
                raise ValueError(f"No schema found for index '{self.docs_index_name}'.")

            field_names = [prop['name'] for prop in class_schema['properties']]
            field_names.extend([self.text_key, "_additional { vector }", "filename"])

            page_size = 100
            offset = 0

            while True:
                result = client.query.get(
                    self.docs_index_name,
                    [self.text_key, "_additional { vector }", "filename", "_additional { id }"] + field_names
                ).with_limit(page_size).with_offset(offset).do()

                data = result["data"]["Get"][self.docs_index_name]

                if not data:
                    break

                self.data.extend(data)
                offset += page_size

            self._extract_fields(field_names)

    def _extract_fields(self, field_names):
        self.embeddings = [item["_additional"]["vector"] for item in self.data]
        self.texts = [item[self.text_key] for item in self.data]
        self.filenames = [item.get("filename", {}) for item in self.data]
        self.ids = [item["_additional"]["id"] for item in self.data]

        for field in field_names:
            if field not in [self.text_key, "_additional { vector }", "filename"]:
                self.other_fields[field] = [item.get(field, None) for item in self.data]

        self.embedding_array = np.array(self.embeddings)

    def apply_clustering(self):
        kmeans = KMeans(n_clusters=self.num_clusters, random_state=0).fit(self.embedding_array)
        self.labels = kmeans.labels_

    def plot_clusters(self):
        plot_cluster(self.embedding_array, self.labels, self.texts, self.filenames, self.num_clusters, KMeans(n_clusters=self.num_clusters))

    def create_output_files(self, txt_file_path='clustered_data.txt', xlsx_file_path='clustered_data.xlsx'):
        self._create_text_file(txt_file_path)
        self._create_excel_file(xlsx_file_path)

    def _create_text_file(self, output_file_path):
        with open(output_file_path, 'w', encoding='utf-8') as file:
            file.write("Clustered Data:\n")
            file.write("="*40 + "\n")

            for cluster in range(self.num_clusters):
                cluster_docs = [e for e in self._get_clustered_data() if e['cluster'] == cluster]
                file.write(f"Cluster {cluster}:\n")
                for doc in cluster_docs:
                    file.write(f"Filename: {doc['filename']}\n")
                    file.write(f"text_as_html: {doc['text_as_html']}\n")
                    file.write("="*20 + "\n")
                file.write("="*40 + "\n")

    def _create_excel_file(self, output_file_path):
        data_dict = {
            'id': self.ids,
            'cluster': self.labels,
            'filenames': self.filenames,
            'texts': self.texts,
        }
        for field in self.other_fields:
            data_dict[field] = self.other_fields[field]

        clustered_df = pd.DataFrame(data_dict)
        clustered_df.to_excel(output_file_path, index=False)

        apply_excel_formatting(
            file_path=output_file_path,
            wrap_columns=['D', 'F'],
            freeze_row='A2',
            table_style="TableStyleMedium9"
        )

    def _get_clustered_data(self):
        clustered_data = []
        for i in range(len(self.embeddings)):
            data_point = {
                'embedding': self.embeddings[i],
                'text': self.texts[i],
                'filename': self.filenames[i],
                'cluster': self.labels[i],
                'id': self.ids[i]
            }
            for field in self.other_fields:
                data_point[field] = self.other_fields[field][i]
            clustered_data.append(data_point)
        return clustered_data

    def compute_cosine_similarity(self):
        similarity_matrix = cosine_similarity(self.embedding_array)
        return similarity_matrix

    def rank_clusters_by_variation(self):
        variation_scores = []
        for cluster in range(self.num_clusters):
            cluster_embeddings = self.embedding_array[self.labels == cluster]
            if len(cluster_embeddings) > 1:
                variation_score = cosine_similarity(cluster_embeddings).mean()
            else:
                variation_score = 0
            variation_scores.append((cluster, variation_score))
        ranked_clusters = sorted(variation_scores, key=lambda x: x[1], reverse=True)
        return ranked_clusters

# Example usage
if __name__ == "__main__":
    pruner = VectorStorePruner(
        weaviate_url=os.getenv("WEAVIATE_URL"),
        weaviate_api_key=os.getenv("WEAVIATE_API_KEY"),
        docs_index_name='JACSKE_HDD',
        record_manager_db_url=os.getenv('RECORD_MANAGER_DB_URL')
    )

    pruner.fetch_data()
    pruner.apply_clustering()
    pruner.plot_clusters()
    pruner.create_output_files()
    similarity_matrix = pruner.compute_cosine_similarity()
    ranked_clusters = pruner.rank_clusters_by_variation()
    print(ranked_clusters)

```



```python
# plotly_project\Clustering_and_Delete_Weaviate_Embeddings1.py

import sys
import os
# from contextlib import contextmanager
# from langchain_community.vectorstores import Weaviate
from sklearn.cluster import KMeans
from sklearn.manifold import TSNE
import numpy as np
# import weaviate
import pandas as pd
from dotenv import load_dotenv
# from sklearn.manifold import TSNE
# from sklearn.metrics import silhouette_score
# from sklearn.metrics.pairwise import cosine_similarity
# import plotly.express as px
# import plotly.graph_objs as go
# import matplotlib.pyplot as plt
# from langchain.indexes import SQLRecordManager
# from Excel_Formating import apply_excel_formatting
from generate_plot import plot_cluster
# from weaviate.auth import AuthApiKey
from Run_API_Server_Files import run_api_server
from weaviate_recordmanager_utils.record_manager_util import RecordManager_Util
from clustering_utils2 import determine_optimal_clusters
import pprint


import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Load environment variables
load_dotenv()
# Initialize Weaviate client
WEAVIATE_URL = os.environ.get("WEAVIATE_URL")
WEAVIATE_API_KEY = os.environ.get("WEAVIATE_API_KEY")
WEAVIATE_DOCS_INDEX_NAME = 'JACSKE_Program'
TEXT_KEY = 'page_content'
num_clusters = 35  # Define the number of clusters
max_clusters = 40
RECORD_MANAGER_DB_URL = os.getenv('RECORD_MANAGER_DB_URL')

RM = RecordManager_Util(
    WEAVIATE_URL,
    WEAVIATE_API_KEY,
    WEAVIATE_DOCS_INDEX_NAME,
    RECORD_MANAGER_DB_URL,
    text_key=TEXT_KEY
)

with RM.get_weaviate_client() as client:
    try:

        prunning_fields_types = {
            'clusterID': ('int', -1),#'-1' indicated 'no cluster assigned
            'tsne_x': ('number', 0),
            'tsne_y': ('number', 0),
            'plot_code': ('int', 1),
            'signature': ('string', 'True')
            # 'plot_params_last_modified': ('date', )#formatted as RFC3339
        }
        prun_fields = list(prunning_fields_types.keys())

        check_field, _ = RM._check_valid_fields(client, 'use4RAG')
        if not check_field: #Index hasn't been processed before. Add all prunning fields
            RM.add_new_field(client, 'use4RAG', 'boolean', True)
            check_field, _ = RM._check_valid_fields(client, prun_fields)
            field_to_add = [key for key in prunning_fields_types.keys() if key not in check_field]
            if field_to_add:        
                for field in field_to_add:
                    field_type = prunning_fields_types[field][0]
                    default_value = prunning_fields_types[field][1]
                    RM.add_new_field(client, field, field_type, default_value)#'-1' indicated 'no cluster assigned
 
        else:#Index has been processed. Reset prunning fields to default values is users approves
            reprune = input("""\
The selected index has already been pruned using clustering. Would you like to reprune (y/n)?
""")
            if reprune.lower() == 'y' or reprune.lower() == 'yes':
                RM._update_all_field_values(client, 'use4RAG', True)
                check_field, _ = RM._check_valid_fields(client, prun_fields)
                field_to_add = [key for key in prunning_fields_types.keys() if key not in check_field]
                if field_to_add:        
                    for field in field_to_add:
                        field_type = prunning_fields_types[field][0]
                        default_value = prunning_fields_types[field][1]
                        RM.add_new_field(client, field, field_type, default_value)#'-1' indicated 'no cluster assigned
 
                if check_field:
                    for field in check_field:
                        field_type = prunning_fields_types[field][0]
                        default_value = prunning_fields_types[field][1]
                        RM._update_all_field_values(client, field, default_value)
            else:
                exit()


        page_size=100 #paginate
        all_data = RM.get_all_data(client, page_size=page_size)

        # Extract embeddings, texts, metadata, and IDs from the results
        embeddings = [item.get("vector", {}) for item in all_data]
        texts = [item.get(TEXT_KEY, {}) for item in all_data]
        filenames = [item.get("filename", {}) for item in all_data]
        ids = [item["id"] for item in all_data]

        # Extract all other fields dynamically using dictionary comprehension to filter the data
        excluded_fields = {TEXT_KEY, "vector", "filename", 'id'}

        other_fields = [
            {
                field_name: field_value
                for field_name, field_value in item.items()
                if field_name not in excluded_fields
            }
            for item in all_data
        ]

        # Extract all other fields dynamically
        # other_fields = {}
        # for data in all_data:
        #     if field not in [TEXT_KEY, "vector", "filename", 'id']:
        #         other_fields[field] = [item.get(field, None) for item in all_data]

        # Convert embeddings to numpy array for clustering
        embedding_array = np.array(embeddings)

        # # Add cluster labels back to your data
        # clustered_data = []
        # for i in range(len(embeddings)):
        #     data_point = {
        #         'embedding': embeddings[i],
        #         'text': texts[i],
        #         'filename': filenames[i],
        #         'cluster': labels[i],
        #         'id': ids[i]
        #     }
        #     for field in other_fields:
        #         data_point[field] = other_fields[field][i]
        #     clustered_data.append(data_point)



        # num_clusters = optimal_cluster_count(embedding_array, max_clusters=num_clusters)
        if max_clusters >= len(all_data):
            print(f"""
'max_clusters' is set to {max_clusters}. 'all_Data' contains {len(all_data)} samples. \
'max_clusters' must be set to a value between 2 and n_samples - 1 ({len(all_data)-1}). \
Setting 'max_clusters' to maximum value (max_clusters = {len(all_data)-1}).
""")
            max_clusters = len(all_data)-1
        elif max_clusters < 2:
            print(f"""
'max_clusters' is set to {max_clusters}. \
'max_clusters' must be set to a value between 2 and n_samples - 1 ({len(all_data)-1}). \
Setting 'max_clusters' to minimum value of 2.
""")
            max_clusters = 2
            
        num_clusters = determine_optimal_clusters(embedding_array,max_clusters=max_clusters, use_gpu=False)
        print(f'Optimal number of clusters: {num_clusters}')

        # Apply k-means clustering
        kmeans = KMeans(n_clusters=num_clusters, random_state=0).fit(embedding_array)
        # Get cluster labels
        labels = kmeans.labels_


        # Automatically determine perplexity
        perplexity = min(50, max(5, int(np.sqrt(len(embedding_array)))))    

        # Relationship visualization using t-SNE
        tsne = TSNE(n_components=2, random_state=0,perplexity=perplexity)
        tsne_results = tsne.fit_transform(embedding_array)

        tsne_x = []
        tsne_y = []
        for x0,y0 in tsne_results:
            tsne_x.append(x0)
            tsne_y.append(y0)


        RM.set_field_values_by_id(client, ids, 'tsne_x', tsne_x)
        RM.set_field_values_by_id(client, ids, 'tsne_y', tsne_y)

        clusterID = labels.astype(int).tolist()
        RM.set_field_values_by_id(client, ids, 'clusterID', clusterID)


        # Plot the cluster using the imported function
        # plot_cluster(embedding_array, labels, texts, ids, filenames, num_clusters, kmeans)
        # plot_cluster(RM, client,embedding_array, labels, texts, ids, filenames, num_clusters, kmeans)
        
        try:
            run_api_server('.\\plotly_project\\app.py')
        except Exception as e:
            print(f"Failed to start API server: {e}")

#         # Define the output file path
#         output_file_path = 'clustered_data.txt'

#         # Open the file in write mode with UTF-8 encoding
#         with open(output_file_path, 'w', encoding='utf-8') as file:
#             # Write header
#             file.write("Clustered Data:\n")
#             file.write("="*40 + "\n")

#             # Write cluster information
#             for cluster in range(num_clusters):
#                 cluster_docs = [e for e in clustered_data if e['cluster'] == cluster]
#                 file.write(f"Cluster {cluster}:\n")
#                 for doc in cluster_docs:
#                     file.write(f"Filename: {doc['filename']}\n")
#                     file.write(f"text_as_html: {doc['text_as_html']}\n")
#                     file.write("="*20 + "\n")
#                 file.write("="*40 + "\n")

            
#         # Define the output file path
#         output_file_path = 'clustered_data.xlsx'

#         # Create a DataFrame with the required columns
#         data_dict = {
#             'id': ids,
#             'cluster': labels,
#             'filenames': filenames,
#             'texts': texts,
#         }
#         for field in other_fields:
#             data_dict[field] = other_fields[field]

#         clustered_df = pd.DataFrame(data_dict)

        
#         count_retry = 0     
#         def write_data_to_excel_file(output_file_path, ):
#             # Write the DataFrame to an .xlsx file
#             clustered_df.to_excel(output_file_path, index=False)

#             # Format Excel Spreadsheet
#             apply_excel_formatting(
#                 file_path=output_file_path,
#                 wrap_columns=['D', 'F'],
#                 freeze_row='A2',
#                 table_style="TableStyleMedium9"
#             )
#             return 1
#         try:  
#             write_data_to_excel_file(output_file_path)
#         except:
#             user_response = input(f"""\
# The excel file: {output_file_path} may be open. Close the file and press \
# enter to continue. To stop execution, type 'stop'./
# """)
#             if user_response.lower == 'stop':
#                 print(f"""Stopping execution.""")
#                 exit()
            
#             if count_retry >2:
#                 print(f"""Not able to write to excel file: {output_file_path}. Stopping execution.""")
#                 exit()
                
#             count_retry = write_data_to_excel_file(output_file_path)+1

    finally:
        pass  # No need to close the client as it doesn't have a close method


# Pause for user to examine data
input("Examine the data. Press Enter to continue...")

```

```python
# plotly_project\Clustering_and_Delete_Weaviate_Embeddings2.py


import os
from sklearn.cluster import KMeans
from sklearn.manifold import TSNE
import numpy as np
from dotenv import load_dotenv
from weaviate_recordmanager_utils.record_manager_util import RecordManager_Util
from clustering_utils2 import determine_optimal_clusters


import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Load environment variables
load_dotenv()
# Initialize Weaviate client
WEAVIATE_URL = os.environ.get("WEAVIATE_URL")
WEAVIATE_API_KEY = os.environ.get("WEAVIATE_API_KEY")
TEXT_KEY = 'page_content'
max_clusters = 40
RECORD_MANAGER_DB_URL = os.getenv('RECORD_MANAGER_DB_URL')


def calc_tsne_and_clusters(
        WEAVIATE_DOCS_INDEX_NAME,
        max_clusters=40,
        min_clusters=2,
        force_reinitialize=False, 
        recalc_tsne_clusters_only=False
):
    

    RM = RecordManager_Util(
        WEAVIATE_URL,
        WEAVIATE_API_KEY,
        WEAVIATE_DOCS_INDEX_NAME,
        RECORD_MANAGER_DB_URL,
        text_key=TEXT_KEY
    )

    with RM.get_weaviate_client() as client:
        try:

            prunning_fields_types = {
                'clusterID': ('int', -1),#'-1' indicated 'no cluster assigned
                'tsne_x': ('number', 0),
                'tsne_y': ('number', 0),
                'plot_code': ('int', 1),
                'signature': ('string', 'True')
                # 'plot_params_last_modified': ('date', )#formatted as RFC3339
            }
            prun_fields = list(prunning_fields_types.keys())

            check_field, _ = RM._check_valid_fields(client, 'use4RAG')
            if not check_field: #Index hasn't been processed before. Add all prunning fields
                RM.add_new_field(client, 'use4RAG', 'boolean', True)
                check_field, _ = RM._check_valid_fields(client, prun_fields)
                field_to_add = [key for key in prunning_fields_types.keys() if key not in check_field]
                if field_to_add:        
                    for field in field_to_add:
                        field_type = prunning_fields_types[field][0]
                        default_value = prunning_fields_types[field][1]
                        RM.add_new_field(client, field, field_type, default_value)#'-1' indicated 'no cluster assigned
    
            elif force_reinitialize:#Index has been processed. Reset prunning fields to default values if users approves
                RM._update_all_field_values(client, 'use4RAG', True)
                check_field, _ = RM._check_valid_fields(client, prun_fields)
                field_to_add = [key for key in prunning_fields_types.keys() if key not in check_field]
                if field_to_add:        
                    for field in field_to_add:
                        field_type = prunning_fields_types[field][0]
                        default_value = prunning_fields_types[field][1]
                        RM.add_new_field(client, field, field_type, default_value)#'-1' indicated 'no cluster assigned

                if check_field:
                    for field in check_field:
                        field_type = prunning_fields_types[field][0]
                        default_value = prunning_fields_types[field][1]
                        RM._update_all_field_values(client, field, default_value)
            elif not recalc_tsne_clusters_only:
                return """\
Index has already been initialized for pruning. Set 'force_reinitialize' flag to 'True' to reinitialize \
or set 'recalc_tsne_clusters_only' to 'True' to recalculate T-SNE and Clusters\
"""

            all_data = RM.get_all_data(client)

            # Extract embeddings, texts, metadata, and IDs from the results
            embeddings = [item.get("vector", {}) for item in all_data]
            ids = [item["id"] for item in all_data]

            # Convert embeddings to numpy array for clustering
            embedding_array = np.array(embeddings)

            greater_than_length_message = f"""
    'max_clusters' is set to {max_clusters}. 'all_Data' contains {len(all_data)} samples. \
    'max_clusters' must be set to a value between {min_clusters} and n_samples - 1 ({len(all_data)-1}). \
    Setting 'max_clusters' to maximum value (max_clusters = {len(all_data)-1}).
    """
            less_than_two_message = f"""
    'max_clusters' is set to {max_clusters}. \
    'max_clusters' must be set to a value between {min_clusters} and n_samples - 1 ({len(all_data)-1}). \
    Setting 'max_clusters' to minimum value of {min_clusters}.
    """     

            if max_clusters >= len(all_data):
                print(greater_than_length_message)
                max_clusters = len(all_data)-1
            elif max_clusters < min_clusters:
                print(less_than_two_message)
                max_clusters = min_clusters
        
            num_clusters = determine_optimal_clusters(embedding_array,max_clusters=max_clusters,min_clusters=min_clusters, use_gpu=False)
            print(f'Optimal number of clusters: {num_clusters}')

            # Apply k-means clustering
            kmeans = KMeans(n_clusters=num_clusters, random_state=0).fit(embedding_array)
            # Get cluster labels
            labels = kmeans.labels_


            # Automatically determine perplexity
            perplexity = min(50, max(5, int(np.sqrt(len(embedding_array)))))    

            # Relationship visualization using t-SNE
            tsne = TSNE(n_components=2, random_state=0,perplexity=perplexity)
            tsne_results = tsne.fit_transform(embedding_array)

            tsne_x = []
            tsne_y = []
            for x0,y0 in tsne_results:
                tsne_x.append(x0)
                tsne_y.append(y0)


            RM.set_field_values_by_id(client, ids, 'tsne_x', tsne_x)
            RM.set_field_values_by_id(client, ids, 'tsne_y', tsne_y)

            clusterID = labels.astype(int).tolist()
            RM.set_field_values_by_id(client, ids, 'clusterID', clusterID)
            
            return

        except Exception as e:
            print(f"Error initializing database: {e}")

    
```

```python
# plotly_project\clustering_utils.py

import cupy as cp
from sklearn.metrics import pairwise_distances
from sklearn.cluster import KMeans
import numpy as np
import matplotlib.pyplot as plt

def silhouette_score_gpu(X, labels):
    # Move data to GPU
    X_gpu = cp.asarray(X)
    labels_gpu = cp.asarray(labels)
    
    # Calculate pairwise distances on the GPU
    X_np = cp.asnumpy(X_gpu)  # Convert to NumPy array
    pairwise_distances_np = pairwise_distances(X_np, metric='euclidean')  # Calculate distances with NumPy array
    pairwise_distances_gpu = cp.asarray(pairwise_distances_np)  # Convert back to CuPy array
    
    # Calculate silhouette score components on the GPU
    A = cp.mean(pairwise_distances_gpu, axis=1)
    B = cp.zeros_like(A)
    
    for label in cp.unique(labels_gpu):
        mask = (labels_gpu == label)
        cluster_distances = pairwise_distances_gpu[mask]
        B[mask] = cp.min(cp.mean(cluster_distances, axis=1, keepdims=True), axis=1)
    
    silhouette_scores = (B - A) / cp.maximum(A, B)
    return cp.mean(silhouette_scores).get()

def determine_optimal_clusters_silhouette_gpu(embedding_array, max_clusters=10):
    silhouette_scores = []
    for k in range(2, max_clusters+1):
        kmeans = KMeans(n_clusters=k, random_state=0).fit(embedding_array)
        labels = kmeans.labels_
        score = silhouette_score_gpu(embedding_array, labels)
        silhouette_scores.append(score)
    
    # Plot the silhouette scores
    plt.figure(figsize=(8, 4))
    plt.plot(range(2, max_clusters+1), silhouette_scores, marker='o')
    plt.title('Silhouette Score For Optimal k (GPU)')
    plt.xlabel('Number of clusters')
    plt.ylabel('Silhouette Score')
    plt.show()

    optimal_clusters = silhouette_scores.index(max(silhouette_scores)) + 2
    return optimal_clusters

# Example callable function
def optimal_cluster_count(embedding_array, max_clusters=10):
    return determine_optimal_clusters_silhouette_gpu(embedding_array, max_clusters)

# Example usage
if __name__ == "__main__":
    embedding_array = np.random.rand(1000, 50)  # Example embedding array
    num_clusters = optimal_cluster_count(embedding_array, max_clusters=10)
    print(f'Optimal number of clusters: {num_clusters}')

```

```python
# plotly_project\clustering_utils2.py

import cupy as cp
import numpy as np
from sklearn.metrics import silhouette_score
from sklearn.cluster import KMeans
import matplotlib.pyplot as plt
from sklearn.datasets import make_blobs
import multiprocessing
import os

def plot_silhouette_scores(silhouette_scores, max_clusters, min_clusters, use_gpu):
    plt.figure(figsize=(8, 4))
    plt.plot(range(min_clusters, max_clusters + 1), silhouette_scores, marker='o')
    plt.title(f'Silhouette Score For Optimal k ({"GPU" if use_gpu else "CPU"})')
    plt.xlabel('Number of clusters')
    plt.ylabel('Silhouette Score')
    plot_path = 'silhouette_scores.png'
    plt.savefig(plot_path)
    plt.close()
    
    # Open the plot image asynchronously
    if os.name == 'posix':  # For Unix-based systems
        os.system(f'xdg-open {plot_path}')
    elif os.name == 'nt':  # For Windows
        os.system(f'start {plot_path}')

def determine_optimal_clusters(X, max_clusters=35,min_clusters=2, use_gpu=False, plot_on=False):
    silhouette_scores = []
    for k in range(min_clusters, max_clusters + 1):
        kmeans = KMeans(n_clusters=k, random_state=0).fit(X)
        labels = kmeans.labels_
        
        if use_gpu:
            # Convert data to numpy if using GPU for compatibility with sklearn metrics
            X_np = cp.asnumpy(X) if isinstance(X, cp.ndarray) else X
        else:
            X_np = X
        
        score = silhouette_score(X_np, labels)
        silhouette_scores.append(score)
    
    if plot_on:# Create a separate process for plotting
        plot_process = multiprocessing.Process(target=plot_silhouette_scores, args=(silhouette_scores, max_clusters, use_gpu))
        plot_process.start()
    
    optimal_clusters = silhouette_scores.index(max(silhouette_scores)) + min_clusters
    return optimal_clusters

if __name__ == "__main__":
    # Generate some sample data
    X, _ = make_blobs(n_samples=500, centers=4, cluster_std=0.60, random_state=0)

    # Convert to GPU array if desired
    use_gpu = cp.cuda.runtime.getDeviceCount() > 0
    X_gpu = cp.asarray(X) if use_gpu else X

    num_clusters = determine_optimal_clusters(X_gpu, max_clusters=10,min_clusters=2, use_gpu=use_gpu)
    print(f'Optimal number of clusters: {num_clusters}')

```

```python
# plotly_project\config.py

import os
from dotenv import load_dotenv
from pathlib import Path

def load_config():
    load_dotenv()
    CLUSTER_BACKEND_PORT = int(os.getenv('CLUSTER_BACKEND_PORT', '8025'))
    WEAVIATE_DOCS_INDEX_NAME = 'SEPs_F_T_C_W_A_V_Summaries'
    script_directory = Path(__file__).parent
    project_root = script_directory.parent
    plot_directory = project_root / "plotly_project"
    reference_directory = plot_directory / "reference_docs" / WEAVIATE_DOCS_INDEX_NAME
    static_directory = plot_directory / "static"
    index_html = "index.html"
    browser2_html = "browser2.html"
    browser3_html = "browser3.html"
    weaviateui_html = "weaviateui/weaviateui.html"

    index_html_path = static_directory / index_html
    browser2_html_path = static_directory / browser2_html
    browser3_html_path = static_directory / browser3_html
    weaviateui_html_path = static_directory / weaviateui_html

    weaviateUi_settings = {
        "1": "setting1",
        "2": "setting2",
        "3": "setting3",
        "4": "setting4",
        "5": "setting5"
    }

    # Define a dictionary to hold plot configurations
    plot_configs = {
        'scatter_plot': ['clusterID', 'tsne_x', 'tsne_y', 'page_content', 'filename'],
        'bar_plot': ['clusterID'],
        'centroid_plot': ['clusterID', 'tsne_x', 'tsne_y']
    }

    # Automatically generate supported plot types from the keys of the dictionary
    supported_plot_types = list(plot_configs.keys())

    return {
        "CLUSTER_BACKEND_PORT": CLUSTER_BACKEND_PORT,
        "WEAVIATE_DOCS_INDEX_NAME": WEAVIATE_DOCS_INDEX_NAME,
        "static_directory": static_directory,
        "index_html_path": index_html_path,
        "index_html": index_html,
        "browser2_html_path": browser2_html_path,
        "browser2_html": browser2_html,
        "browser3_html_path": browser3_html_path,
        "browser3_html": browser3_html,
        "weaviateui_html_path": weaviateui_html_path,
        "weaviateui_html": weaviateui_html,
        "plot_configs": plot_configs,
        "supported_plot_types": supported_plot_types,
        "weaviateUi_settings": weaviateUi_settings,
        "reference_directory": reference_directory,
        "TEXT_KEY": 'page_content',
        "max_clusters": 60,
        "min_clusters": 5,
    }

```

```python
# plotly_project\custom_weaviate.py

"""
CustomWeaviate Class

Purpose:
This custom wrapper class, CustomWeaviate, was created to extend the functionality 
of the existing Weaviate class from the langchain_community library. The primary 
purpose of this wrapper is to include additional properties, specifically 'vector' 
and 'id', in the results returned by the max_marginal_relevance_search method. This 
extension ensures that these properties are consistently available in the search 
results, providing more detailed information for downstream processing and analysis.

Description:
The CustomWeaviate class inherits from the base Weaviate class and overrides the 
max_marginal_relevance_search and max_marginal_relevance_search_by_vector methods. 
The overridden methods ensure that additional properties like 'vector' and 'id' are 
included in the search results when specified. The implementation includes checks to 
handle cases where these additional properties are not requested, thereby preventing 
KeyErrors and ensuring robust functionality.

Key Features:
- Extends max_marginal_relevance_search to include 'vector' and 'id' in results.
- Includes error handling to manage cases where additional properties are not present.
- Provides detailed metadata for each document returned in the search results.

Library Versions:
- langchain-community: 0.2.4
- weaviate-client: 4.6.5

This custom wrapper is essential for applications requiring enriched metadata in search 
results, particularly in scenarios involving document similarity and relevance ranking.
"""



from langchain_community.vectorstores import Weaviate
from langchain_community.vectorstores.utils import maximal_marginal_relevance

from langchain.schema import Document
from typing import List, Any
import numpy as np

class CustomWeaviate(Weaviate):
    def max_marginal_relevance_search(
        self,
        query: str,
        k: int = 4,
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
        **kwargs: Any,
    ) -> List[Document]:
        if self._embedding is not None:
            embedding = self._embedding.embed_query(query)
        else:
            raise ValueError("max_marginal_relevance_search requires a suitable Embeddings object")

        return self.max_marginal_relevance_search_by_vector(
            embedding, k=k, fetch_k=fetch_k, lambda_mult=lambda_mult, **kwargs
        )

    def max_marginal_relevance_search_by_vector(
        self,
        embedding: List[float],
        k: int = 4,
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
        additional: List[str] = None,
        **kwargs: Any,
    ) -> List[Document]:
        vector = {"vector": embedding}
        query_obj = self._client.query.get(self._index_name, self._query_attrs)
        if kwargs.get("where_filter"):
            query_obj = query_obj.with_where(kwargs.get("where_filter"))
        if kwargs.get("tenant"):
            query_obj = query_obj.with_tenant(kwargs.get("tenant"))

        if additional is None:
            additional = []

        results = (
            query_obj.with_additional(additional)
            .with_near_vector(vector)
            .with_limit(fetch_k)
            .do()
        )

        payload = results["data"]["Get"][self._index_name]

        if 'vector' in additional:
            embeddings = [result["_additional"]["vector"] for result in payload]
            mmr_selected = maximal_marginal_relevance(
                np.array(embedding), embeddings, k=k, lambda_mult=lambda_mult
            )
        else:
            mmr_selected = range(min(len(payload), k))

        docs_and_scores = []
        for idx in mmr_selected:
            text = payload[idx].pop(self._text_key)
            meta = payload[idx]
            score = None
            if 'vector' in additional:
                vector = payload[idx]["_additional"]["vector"]
                meta["vector"] = vector
            if 'id' in additional:
                doc_id = payload[idx]["_additional"]["id"]
                meta["id"] = doc_id
            if 'score' in additional:
                score = np.dot(vector, embedding)  # Calculate the score
                meta["score"] = score  # Add the score to metadata
            payload[idx].pop("_additional", None)
            docs_and_scores.append(Document(page_content=text, metadata=meta))
        return docs_and_scores

```

```python
# plotly_project\Excel_Formating.py

import openpyxl
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.styles import Alignment
from openpyxl.worksheet.table import Table, TableStyleInfo
import pandas as pd

# Your existing imports and code...

def apply_excel_formatting(file_path, wrap_columns, freeze_row, table_style):
    # Open the created Excel file with openpyxl
    wb = openpyxl.load_workbook(file_path)
    ws = wb.active

    # Wrap text in specified columns
    for col in wrap_columns:
        for cell in ws[col]:
            cell.alignment = Alignment(wrap_text=True)

    # Freeze the specified row
    ws.freeze_panes = ws[freeze_row]

    # Make all columns filterable
    table = Table(displayName="Table1", ref=ws.dimensions)
    style = TableStyleInfo(
        name=table_style, 
        showFirstColumn=False,
        showLastColumn=False, 
        showRowStripes=True, 
        showColumnStripes=True
    )
    table.tableStyleInfo = style
    ws.add_table(table)

    # Save the changes
    wb.save(file_path)



# # Using this function

# # Call the formatting function
# apply_excel_formatting(
#     file_path=output_file_path,
#     wrap_columns=['D', 'F'],
#     freeze_row='A2',
#     table_style="TableStyleMedium9"
# )

```

```python
# plotly_project\fix_acronym_lists.py

import os
from langchain.chains import LLMChain
from langchain.prompts import ChatPromptTemplate
from langchain.schema import BaseOutputParser
from openai import AzureOpenAI
import json
from Update_Weaviate import get_weaviate_ids_from_field_values, weaviate_client

api_version = "2024-02-01"
model_4 = "gpt-4"
deployment_name = model_4
embedder_model = "text-embedding-ada-002"
NUMBER_OF_DOCS_RETRIEVED = 1
MAX_RETRIES = 3

WEAVIATE_URL = os.environ.get("WEAVIATE_URL")
WEAVIATE_API_KEY = os.environ.get("WEAVIATE_API_KEY")
WEAVIATE_DOCS_INDEX_NAME = 'SEPs_F_T_C_W_A_V' 

llm = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"), 
    api_key=os.getenv("AZURE_OPENAI_API_KEY"), 
    api_version=api_version,
)


# Define the prompt
system_prompt = """
Given the following text, determine if it is an acronym list. If it is, respond with a dictionary format:
{
    "acronyms": {
        "acronym1": "Acronym Definition",
        "acronym2": "Acronym Definition",
        "acronym3": "Acronym Definition"
    }
}
If it is not an acronym list, respond with:
{
    "acronyms": None
}
"""

def get_acronym_list(text):
    response = llm.chat.completions.create(
        model = "gpt-4",
        messages=[
            {"role": "system", "content": system_prompt},
            # {"role": "user", "content": html_1shota},
            # {"role": "assistant", "content": html_1shotb},
            {"role": "user", "content": text},
        ]
    )
    response0 = json.loads(response.choices[0].message.content.strip())
    return response0


with weaviate_client(WEAVIATE_URL, WEAVIATE_API_KEY) as client:

    ids = []
    for element in elements:
        acronym_list = get_acronym_list(element.page_content)
        if acronym_list:
            file_path = element.metadata.file_path
            ids = get_weaviate_ids_from_field_values(client,WEAVIATE_DOCS_INDEX_NAME, 'file_path', file_path)
    print(ids)
# # Example usage
# def process_text(text: str) -> dict:
#     return get_acronym_list(text)

# # Example input text
# text = """
# The recent advancements in technology have brought significant changes in various fields. A notable example is the rise of AI: Artificial Intelligence, which is revolutionizing industries. Moreover, companies are heavily investing in ML: Machine Learning, transforming data analytics. The field of NLP: Natural Language Processing is also gaining traction, enabling better human-computer interactions. However, there have been reports that...

# ...the integration of AI: Artificial Intelligence and ML: Machine Learning presents unique challenges. For instance, in some applications, the accuracy of ML: Machine Learning models can be affected by data quality. Similarly, implementing NLP: Natural Langage Processing in real-time systems has its own set of difficulties.

# In addition, there is a growing concern about the ethical implications of AI: Artificial Intelligenc and its impact on privacy. Researchers are focusing on making ML: Machine Learnin more transparent and fair. This ongoing debate highlights the need for responsible development of these technologies.

# Furthermore, combining AI: Artificial Intelligence, ML: Machine Learning, and NLP: Natural Language Processin can lead to innovative solutions. Yet, the scalability of these technologies remains a critical issue. Efforts are being made to overcome these barriers and enhance the efficiency of AI: Artifical Intelligence systems.

# In conclusion, while AI: Artificial Intelligence, ML: Machine Learning, and NLP: Natural Language Processing hold great promise, it is crucial to address the associated challenges. Continued research and ethical considerations will play a vital role in the sustainable development of these fields.
# """

# # Process the text
# result = process_text(text)
# print(result)

```

```python
# plotly_project\generate_plot.py

## generate_plots.py

import plotly.express as px
import numpy as np
import pandas as pd
from sklearn.manifold import TSNE
import json
import os
from pathlib import Path
from sklearn.cluster import KMeans

# Determine the directory where the script is located
script_directory = Path(__file__).parent
# Navigate one level up to the project's root folder
project_root = script_directory.parent
# Define the plot directory relative to the project's root folder
plot_directory = project_root / "plotly_project"

def save_data_as_json(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f)

# def plot_cluster(embedding_array, clusterID, texts, id, filename, num_clusters, kmeans):
def plot_cluster(db, client):#,embedding_array, clusterID, texts, id, filename, num_clusters, kmeans):


    plot_data= db.get_filtered_data(client, 'use4RAG', True, ['clusterID', 'tsne_x', 'tsne_y', 'page_content', 'filename'], True)

    clusterID = []
    tsne_x = []
    tsne_y = []
    texts = [] #using 'text' as 'page_content' for conciseness
    filename = []
    id = []
    embeddings = []

    for pd in plot_data:
        clusterID.append(pd['clusterID'])
        tsne_x.append(pd['tsne_x'])
        tsne_y.append(pd['tsne_y'])
        texts.append(pd['page_content'])
        filename.append(pd['filename'])
        id.append(pd['id'])
        embeddings.append(pd['embeddings'])

    embedding_array = np.array(embeddings)
    num_clusters = len(clusterID)

    # # Automatically determine perplexity
    # perplexity = min(30, max(5, int(np.sqrt(len(embedding_array)))))    

    # # Relationship visualization using t-SNE
    # tsne = TSNE(n_components=2, random_state=0,perplexity=perplexity)
    # tsne_results = tsne.fit_transform(embedding_array)


    # # Create DataFrame for visualization
    # df = pd.DataFrame(tsne_results, columns=['tsne1', 'tsne2'])
    # df['cluster'] = clusterID
    # df['filename'] = filename
    # df['content'] = texts# [text[:80] for text in texts]
    # df['id'] = id

    # # Save data to JSON
    # plot_data = df.to_dict(orient='records')

    # scat_file = plot_directory / "scatter_plot_data.json"
    # save_data_as_json(scat_file, plot_data)

    # Create an interactive scatter plot using Plotly
    fig_scatter = px.scatter(
        df, x='tsne1', y='tsne2', color='cluster',
        hover_data={'filename': True, 'content': True},
        title='t-SNE Clustering of Documents', width=800, height=600
    )

    # Create buttons for each cluster, sorted by cluster number
    clusters = sorted(set(clusterID))
    buttons = []
    for i in clusters:
        visible = [True if cluster == i else False for cluster in clusterID]
        buttons.append(dict(
            method='update',
            label=f'Cluster {i}',
            args=[{'visible': visible}, {'title': f'Cluster {i}'}]
        ))

    # Add a button to show all clusters
    buttons.append(dict(
        method='update',
        label='All',
        args=[{'visible': [True] * len(clusterID)}, {'title': 'All Clusters'}]
    ))

    fig_scatter.update_layout(
        updatemenus=[{
            'buttons': buttons,
            'direction': 'down',
            'showactive': True
        }]
    )

    # Save scatter plot to HTML
    scat_html_file = plot_directory / "scatter_plot.html"
    fig_scatter.write_html(scat_html_file, full_html=False, include_plotlyjs='cdn')

    # 1. Cluster Distribution Bar Plot
    cluster_counts = pd.Series(clusterID).value_counts().sort_index()
    fig_bar = px.bar(
        cluster_counts,
        x=cluster_counts.index,
        y=cluster_counts.values,
        clusterID={'index': 'Cluster', 'value': 'Number of Documents'},
        title='Cluster Distribution'
    )

    # Save data to JSON
    bar_plot_data = {
        'x': cluster_counts.index.tolist(),
        'y': cluster_counts.values.tolist()
    }
    bar_file = plot_directory / "bar_plot_data.json"
    save_data_as_json(bar_file, bar_plot_data)

    # Save bar plot to HTML
    bar_html_file = plot_directory / "bar_plot.html"
    fig_bar.write_html(bar_html_file, full_html=False, include_plotlyjs='cdn')

    # 2. Cluster Centroid Visualization
    centroids = kmeans.cluster_centers_
    centroid_perplexity = min(30, max(5, int(np.sqrt(len(centroids)))))
    tsne_centroids = TSNE(n_components=2, random_state=0, perplexity=centroid_perplexity).fit_transform(centroids)
    # tsne_centroids = tsne.fit_transform(centroids)
    df_centroids = pd.DataFrame(tsne_centroids, columns=['tsne1', 'tsne2'])
    df_centroids['cluster'] = range(num_clusters)

    fig_centroids = px.scatter(
        df_centroids, x='tsne1', y='tsne2', color='cluster',
        title='t-SNE Visualization of Cluster Centroids', width=800, height=600
    )

    fig_centroids.update_layout(
        legend_title_text='Cluster Centroid'
    )

    # Save data to JSON
    centroid_plot_data = df_centroids.to_dict(orient='records')
    centroid_file = plot_directory / "centroid_plot_data.json"
    save_data_as_json(centroid_file, centroid_plot_data)

    # Save centroid plot to HTML
    centroid_html_file = plot_directory / "centroid_plot.html"
    fig_centroids.write_html(centroid_html_file, full_html=False, include_plotlyjs='cdn')

    # Define the path to the file
    selected_embeddings_path = plot_directory / "selected_embeddings.json"

    # Check if the file exists
    if selected_embeddings_path.exists():
        # Remove the file
        os.remove(selected_embeddings_path)
        print(f"File {selected_embeddings_path} has been deleted.")
    else:
        print(f"File {selected_embeddings_path} does not exist.")

# # Example usage
# if __name__ == "__main__":
#     # Mock data for demonstration purposes
#     embedding_array = np.random.rand(100, 50)
#     clusterID = np.random.randint(0, 5, 100)
#     texts = ["Sample text"] * 100
#     id = [f"id_{i}" for i in range(100)]
#     filename = [f"file_{i}.txt" for i in range(100)]
#     num_clusters = 5
#     kmeans = KMeans(n_clusters=num_clusters, random_state=0).fit(embedding_array)

#     plot_cluster(embedding_array, clusterID, texts, id, filename, num_clusters, kmeans)

```

```python
# plotly_project\middleware.py

from fastapi.middleware.cors import CORSMiddleware

def setup_middleware(app):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

```

```python
# plotly_project\models.py

from pydantic import BaseModel
from typing import List, Optional

class Config(BaseModel):
    port: int

class RemovePointsRequest(BaseModel):
    selected_ids: List[str]

class Settings(BaseModel):
    setting1: Optional[str] = None
    setting2: Optional[str] = None
    setting3: Optional[str] = None
    setting4: Optional[str] = None
    setting5: Optional[str] = None
```

```python
# plotly_project\OLD_weaviate_v4_recordmanager_utils.py

import os
import json
import weaviate
from contextlib import contextmanager
from weaviate.classes.init import Auth
from weaviate.classes.query import MetadataQuery, Filter, Sort
from dotenv import load_dotenv
# from .ExtendedSQLRecordManager import ExtendedSQLRecordManager, UpsertionRecord
from sqlalchemy import create_engine, text
import pprint
import numpy as np
import numbers
from weaviate_recordmanager_utils.weaviate_V4_client_singleton import get_weaviate_client as singleton_weaviate_client
from weaviate_recordmanager_utils.weaviate_V4_client_singleton import close_weaviate_client
from weaviate.classes.config import Property, DataType
import weaviate.classes as wvc
from weaviate.types import UUID
from weaviate.exceptions import UnexpectedStatusCodeError

import logging
logger = logging.getLogger(__name__)

ID_FIELD_NAME = "_additional { id }"
VECTOR_FIELD_NAME = "_additional { vector }"

def determine_data_type(value):
    if isinstance(value, list):
        return "text[]"
    elif isinstance(value, int):
        return "int"
    elif isinstance(value, float):
        return "number"
    elif value is None:
        return "text"
    else:
        return "text"
    

DATATYPES = {
    'text': DataType.TEXT,               # Text data type
    'text[]': DataType.TEXT_ARRAY,       # Text array data type
    'int': DataType.INT,                 # Integer data type
    'int[]': DataType.INT_ARRAY,         # Integer array data type
    'boolean': DataType.BOOL,            # Boolean data type
    'boolean[]': DataType.BOOL_ARRAY,    # Boolean array data type
    'number': DataType.NUMBER,           # Number data type
    'number[]': DataType.NUMBER_ARRAY,   # Number array data type
    'date': DataType.DATE,               # Date data type
    'date[]': DataType.DATE_ARRAY,       # Date array data type
    'uuid': DataType.UUID,               # UUID data type
    'uuid[]': DataType.UUID_ARRAY,       # UUID array data type
    'geoCoordinates': DataType.GEO_COORDINATES,  # Geo coordinates data type
    'blob': DataType.BLOB,               # Blob data type
    'phoneNumber': DataType.PHONE_NUMBER, # Phone number data type
    'object': DataType.OBJECT,           # Object data type
    'object[]': DataType.OBJECT_ARRAY    # Object array data type
}

class RecordManager_Util:
    def __init__(self, weaviate_url=None, weaviate_api_key=None, docs_index_name=None, record_man_url=None, singleton=False, text_key='page_content'):
        """
        Initializes the RecordManager_Util class.

        Parameters:
        - weaviate_url: URL for Weaviate instance.
        - weaviate_api_key: API key for Weaviate.
        - docs_index_name: The index name for documents in Weaviate (optional).
        - record_man_url: URL for the record manager (optional).
        - text_key: The key to use for text content (optional).
        """
        load_dotenv()  # Load environment variables

        self.text_key = text_key
        self.docs_index_name = docs_index_name
        self.record_man_url = record_man_url or os.getenv('RECORD_MANAGER_DB_URL')
        self.record_manager = None

        if docs_index_name and record_man_url:
            self.record_manager = self.init_record_manager()

        self.weaviate_url = weaviate_url or os.getenv('WEAVIATE_URL')
        self.weaviate_api_key = weaviate_api_key or os.getenv('WEAVIATE_API_KEY')

        # Parse the Weaviate URL to extract host and port
        self.host, self.port = self._parse_weaviate_url(self.weaviate_url)

        self.client = self.get_singleton_weaviate_client()

        self.collection_config = self.get_collection_def()
        self.properties = self.get_properties()

    def _parse_weaviate_url(self, weaviate_url):
        """
        Helper method to parse the Weaviate URL to extract host and port.

        Parameters:
        - weaviate_url: The URL for the Weaviate instance.

        Returns:
        - host: The host part of the URL.
        - port: The port part of the URL.
        """
        if weaviate_url:
            host = weaviate_url.split("//")[-1].split(":")[0]
            port = int(weaviate_url.split(":")[-1])
            return host, port
        return None, None

    def get_singleton_weaviate_client(self):
        return singleton_weaviate_client()
    
    def is_client_ready(self):
        return self.client.is_ready()
    
    def close_weaviate_client(self):
        return close_weaviate_client()

    @contextmanager
    def get_weaviate_client(self, weaviate_url=None, weaviate_api_key=None):
        if not self.weaviate_url or not self.weaviate_api_key:
            if not weaviate_url or not weaviate_api_key:
                raise ValueError("Both weaviate_url and weaviate_api_key must be provided.")
            else:
                self.weaviate_url = weaviate_url
                self.weaviate_api_key = weaviate_api_key
                self.host, self.port = self._parse_weaviate_url(weaviate_url)
        elif weaviate_url or weaviate_api_key:
            raise ValueError("weaviate_url and weaviate_api_key have already been set and cannot be changed.")

        # Create auth credentials
        auth_credentials = Auth.api_key(self.weaviate_api_key)

        # Connect to the Weaviate instance using v4 client
        client = weaviate.connect_to_local(
            host=self.host,
            port=self.port,
            grpc_port=50051,  # Default gRPC port; adjust if necessary
            auth_credentials=auth_credentials
        )

        try:
            yield client
        finally:
            client.close()


    def get_collection(self):
        return self.client.collections.get(self.docs_index_name)

    def get_collection_def(self):
        collection = self.client.collections.get(self.docs_index_name)
        return collection.config.get()


    
    def get_properties(self):
        collection_config = self.collection_config
        docs_index_name = self.docs_index_name

        if not collection_config:
            print(f"No schema found for index '{docs_index_name}'.")
            return None

        # Extract all property names and types
        properties = []
        for prop in collection_config.properties:
            properties.append({
                'name': prop.name,
                'data_type': prop.data_type,
                'description': getattr(prop, 'description', None),
                'index_filterable': getattr(prop, 'index_filterable', None),
                'index_range_filters': getattr(prop, 'index_range_filters', None),
                'index_searchable': getattr(prop, 'index_searchable', None),
                'nested_properties': getattr(prop, 'nested_properties', None),
                'tokenization': getattr(prop, 'tokenization', None),
                'vectorizer_config': getattr(prop, 'vectorizer_config', None),
                'vectorizer': getattr(prop, 'vectorizer', None),
            })

        self.properties = properties
        return self.properties

    # get_metadata_fields
    def get_property_keys(self, property_key):
        """
        Returns a list of values for the specified property key from the properties list.

        Parameters:
        - property_key: A string containing one of the property keys (e.g., 'name', 'data_type', 'description').

        Returns:
        - A list of values corresponding to the property key.
        """
        if not hasattr(self, 'properties') or not self.properties:
            print("Properties list is empty or undefined.")
            return None
        
        # Ensure the property_key is valid
        if not isinstance(property_key, str):
            raise ValueError("property_key must be a string.")

        # Extract values for the given property_key
        values = [prop[property_key] for prop in self.properties if property_key in prop]
        
        if not values:
            print(f"No values found for property '{property_key}'.")
            return None
        
        return values

    def get_field_values(self, field, property_key='name'):
        """
        Retrieves the values for a specified property key from all objects in the collection.

        Parameters:
        - property_key: A string representing the property key.

        Returns:
        - A list of values for the specified property key.
        """
        property_values = []
        if field == 'uuid' or field == 'uuid':
            # Iterate over all objects in the collection
            collection = self.get_collection()
            for item in collection.iterator():
                property_values.append(item.uuid)

        elif field == 'vector' or field == 'vectors':
            # Iterate over all objects in the collection
            collection = self.get_collection()
            for item in collection.iterator():
                property_values.append(item.vector)

        else:
            # Check if the field is in self.get_property_keys(property_key)
            if not hasattr(self, 'properties') or field not in self.get_property_keys(property_key):
                raise ValueError(f"'{property_key}' is not a valid property key.")

            # Iterate over all objects in the collection
            collection = self.get_collection()
            for item in collection.iterator():
                # Append the value of the property to the list if it exists
                if field in item.properties:
                    property_values.append(item.properties[field])
                else:
                    property_values.append(None)  # Handle cases where the property is missing

        return property_values



    def _check_valid_fields(self, field_names):
        docs_index_name = self.docs_index_name

        if isinstance(field_names, str):
            field_names = [field_names]

        count = 0

        valid_field_names = []
        valid_field_types = []
        if 'uuid' in field_names:
            field_names.remove('uuid')
            valid_field_names.append('uuid')
            valid_field_types.append(None)
            count += 1
        if 'vector' in field_names:
            field_names.remove('vector')
            valid_field_names.append('vector')
            valid_field_types.append(None)
            count += 1

        aval_field_names = self.get_property_keys('name')
        aval_field_types = self.get_property_keys('data_type')


        invalid_field_names = []
        # Ensure field_names is a list
        if isinstance(field_names, str):
            if field_names not in aval_field_names and count==0:
                raise ValueError(f"""Field {field_names} is not a valid field name for index {docs_index_name}""")
            else:
                valid_field_names = field_names
                valid_field_types = aval_field_types
        else:
            # Use a list comprehension to filter and extend both lists accordingly
            valid_fields = [(field, aval_field_types[aval_field_names.index(field)]) for field in field_names if field in aval_field_names]

            # Unpack the filtered fields into valid_field_names and valid_field_types
            valid_field_names.extend([field for field, _ in valid_fields])
            valid_field_types.extend([ftype for _, ftype in valid_fields])
            
            if len(field_names) != len(valid_field_names) - count:
                invalid_field_names = [field for field in field_names if field not in aval_field_names]

        if invalid_field_names:
            print(f"Invalid field names removed: {invalid_field_names}")

        return valid_field_names, valid_field_types
    
    def get_data_type(self, data_type_str):
        """
        Looks up the DataType enum corresponding to the provided string.

        Parameters:
        - data_type_str: A string representing the data type (e.g., 'text', 'int', etc.)

        Returns:
        - The corresponding DataType enum value if found, or None if not found.
        """
        data_type_enum = DATATYPES.get(data_type_str)

        if data_type_enum:
            print(f"The DataType for '{data_type_str}' is {data_type_enum}")
        else:
            print(f"No DataType found for '{data_type_str}'")

        return data_type_enum

    def set_field_values_by_ids(self, ids, field_name, value):
        collection = self.get_collection()
        if not isinstance(ids, list):
            ids = [ids]
        
        for uuid in ids:
            try:
                logger.info(f"Attempting to update UUID: {uuid} with field: {field_name} and value: {value}")
                collection.data.update(
                    uuid=uuid,
                    properties={
                        field_name: value,
                    }
                )
                logger.info(f"Successfully updated UUID: {uuid}")



            except UnexpectedStatusCodeError as e:
                if "404" in str(e):  # Checking if the error is a 404
                    logger.error(f"UUID {uuid} not found: {e}")
                else:
                    logger.error(f"Failed to update UUID: {uuid} due to an unexpected error: {e}")
                    raise e  # Re-raise the exception for other status codes

        return


    def set_field_values_for_all_ids(self, field_name,value):
        ids= self.get_field_values('uuid')
        return self.set_field_values_by_ids(ids, field_name,value)

    def add_new_field(self, field_name, field_type, default_value, tokenization=None):

        collection = self.get_collection()

        # Check if the field already exists
        if any(prop== field_name for prop in self.get_property_keys('name')):
            raise ValueError(f"Field '{field_name}' already exists in class '{self.docs_index_name}'.")

        
        collection.config.add_property(
            Property(
                name=field_name,
                data_type=self.get_data_type(field_type)
            )
        )

        return self.set_field_values_for_all_ids(field_name,default_value)

    def get_last_update_to_collection(self):

        collection = self.get_collection()

        response = collection.query.fetch_objects(
            return_metadata=wvc.query.MetadataQuery(last_update_time=True),
            sort=Sort.by_property(name="_lastUpdateTimeUnix", ascending=False),
            limit=1
        )
        
        creation_time = response.objects[0].metadata.last_update_time.isoformat()

        return creation_time # example format: '2024-08-12T18:24:21.725000+00:00'

    def get_filtered_data(
            self, 
            field, 
            value, 
            field_names, 
            vector=False, 
            operator=None, 
            logical_operator=None, 
            return_last_updated_time=False,
            filter_by_last_update_time=None
        ):
        docs_index_name = self.docs_index_name
        # if not isinstance(value, int) and not isinstance(value, list):
        #     value = json.dumps(value)[1:-1]

        if 'uuid' in field:
            if isinstance(field,list):
                if len(field) != 1:
                    field.remove('uuid') 
                    field, field_type = self._check_valid_fields(field)
                    field.append('uuid')
                    field_type.append('string')
                else:
                    field = field[0]
                    field_type = 'string'
            else:
                field = 'uuid'
                field_type = 'string'
        else:
            field, field_type = self._check_valid_fields(field)

        if not field:
            raise ValueError(f"""Field {field} is not a valid field name for index {docs_index_name}""")
        
        # Here we need to replace 'uuid' with ID_FIELD_NAME if 'uuid' is present
        field_names, _ = self._check_valid_fields(field_names)

        if not field_names:
            raise ValueError(f"""field_names {field_names} is not a valid field name for index {docs_index_name}""")
        # Ensure id is always included in the field names

        collection = self.get_collection()
        
        offset = 0
        limit = 200
        all_results = []

        if not operator:
            operator = ['equal' for _ in field]
        elif not isinstance(operator,list):
            operator = [operator]
        if not logical_operator:
            logical_operator= "&"

        if not isinstance(value,list):
            value = [value]

        filters = self.build_filters(field, value, operator, logical_operator,filter_by_last_update_time)

        # last_id = None

        while True:
            response = collection.query.fetch_objects(
                filters=filters,
                limit=limit,
                offset=offset,
                # after=last_id,
                include_vector=vector,
                return_metadata=MetadataQuery(last_update_time=return_last_updated_time)
            )

            # # Cursor
            # last_id = response.objects[-1].uuid

            # Append the current batch of results to the all_results list
            all_results.extend(response.objects)  # Assuming response['objects'] contains the results

            # If the number of results fetched is less than the limit, break the loop
            if len(response.objects) < limit:
                break

            # Increment the offset by the limit to fetch the next batch
            offset += limit

        returned_properties = []
        for o in all_results:
            # Create a new dictionary with only the desired properties
            returned_property = {prop: o.properties[prop] for prop in field_names if prop in o.properties}
            returned_property['uuid'] = str(o.uuid)
            if vector:
                returned_property['vector'] = o.vector
            if return_last_updated_time:
                # RFC3339 format.
                returned_property['return_last_updated_rfc3339_time'] = o.metadata.last_update_time.isoformat()
            returned_properties.append(returned_property)


        # Format the data to include 'uuid' and 'vector' fields appropriately
        return returned_properties

    def build_filters(self, properties, values, operators, logical_operator, last_update_time=None):
        # Start with the first condition
        filter_condition = getattr(Filter.by_property(properties[0]), operators[0])(values[0])

        # Loop through the remaining properties and combine the filters
        for i in range(1, len(properties)):
            new_condition = getattr(Filter.by_property(properties[i]), operators[i])(values[i])
            
            if logical_operator == "&":
                filter_condition = filter_condition & new_condition
            elif logical_operator == "|":
                filter_condition = filter_condition | new_condition
            else:
                raise ValueError(f"Unsupported logical operator: {logical_operator}")
        
        if last_update_time:
            last_update_time_condition = Filter.by_update_time().greater_than(last_update_time)
            filter_condition = filter_condition & last_update_time_condition
           

        return filter_condition   

    def get_data_filter_by_id(self, ids):
        results = []
        collection = self.get_collection()

        # Handle a single str or UUID object
        if isinstance(ids, UUID) or isinstance(ids, str):            
            results = collection.query.fetch_object_by_id(ids)
                
        elif isinstance(ids, list) and (all(isinstance(id, UUID) for id in ids) or all(isinstance(id, str) for id in ids)):
                for id in ids:
                    result = collection.query.fetch_object_by_id(id)
                    results.append(result)
            
        # Raise an error for invalid types
        else:
            raise ValueError(f"""\
id(s) {ids} is not a valid data type. id(s) is type {type(ids)}. \
It should be either a string, a list of strings, a UUID, or a list of UUID objects.""")

        return results
        
        
        

if __name__ == "__main__":
    # Instantiate the class
    weaviate_url =  os.getenv('WEAVIATE_URL')
    weaviate_api_key = os.getenv('WEAVIATE_API_KEY')
    collection = 'SEPs_F_T_C_W_A_V_Summaries'# 'Injected_URL3'#
    try:
        RM= RecordManager_Util(
            weaviate_url=weaviate_url, 
            weaviate_api_key=weaviate_api_key,
            docs_index_name=collection,
            singleton=True,
        )

        
        # Perform operations with the client
        print("Connected to Weaviate:", RM.is_client_ready())


        results = RM.get_filtered_data(
            'use4RAG', 
            True, 
            'text_as_html', 
            return_last_updated_time=True, 
            # filter_by_last_update_time='1723487058.239'
        )

        results = RM.get_last_update_to_collection()
        
        RM.set_field_values_by_ids('87d8e09c-e155-5cb1-9b47-bad70ae8bf2c', 'plot_code', 0)
        ids = RM.get_field_values('uuid')
        RM.set_field_values_for_all_ids('use4RAG',True)
        # results = RM.get_filtered_data('use4RAG', True, 'text_as_html')
        results = RM.get_filtered_data(['use4RAG','page_number'], [True, 1], ['text_as_html','page_number'])
        RM.get_data_filter_by_id(ids[0])
        RM.set_field_values_for_all_ids('test_this','test')
        result = RM.get_field_values('test_this')
        result = RM.get_field_values('uuid')
        RM.add_new_field('test_this', 'text', 'test')
        x, y = RM._check_valid_fields(['uuid', 'use4RAG', 'goodf'])
        result= RM.get_field_values('use4RAG', 'name')

        
        for r in result[:100]:
            print(r)
        print(len(result))
        RM.close_weaviate_client()
        exit()

        value = RM.get_property_keys('name')



        results = RM.get_property_keys('name')
        

        for r in results:
            print(r)

        print('***************')

        aval_field_types = [item['data_type'] for item in results2]
        aval_field_names = [item['name'] for item in results2]

        for r in aval_field_names:
            print(r)

        print('***************')

        for r in aval_field_types:
            print(r)

    finally:
        closer= RecordManager_Util(singleton=True)       
        closer.close_weaviate_client()


```

```python
# plotly_project\rm_operations.py

# rm_operations.py
from weaviate import Client
# from weaviate_recordmanager_utils.record_manager_util import RecordManager_Util
from weaviate_recordmanager_utils.weaviate_v4_recordmanager_utils import RecordManager_Util

# class RMOperations:
#     def __init__(self, docs_index_name: str):
#         self.RM = RecordManager_Util(docs_index_name=docs_index_name)

#     def set_all_ids_visible(self, client: Client):
#         self.RM._update_all_field_values(client, 'plot_code', 1)

#     def set_field_values_by_id(self, client: Client, ids: list, field_name: str, value):
#         self.RM.set_field_values_by_id(client, ids, field_name, value)

#     def set_ids_to_visible(self, client: Client, ids: list):
#         self.RM.set_field_values_by_id(client, ids, 'plot_code', 1)

#     def set_ids_to_nonvisible(self, client: Client, ids: list):
#         self.RM.set_field_values_by_id(client, ids, 'plot_code', 0)

#     def get_filtered_data(self, client: Client, field_name: str, value, fields: list):
#         return self.RM.get_filtered_data(client, field_name, value, fields)
    
#     def get_filtered_by_plot_code(self, client: Client, plot_code, returned_fields: list):
#         return self.RM.get_filtered_data(client, 'plot_code', plot_code, returned_fields)
    
    
#     def get_all_field_names(self, client):
#         return self.RM.get_metadata_fields(client)


class RMOperations:
    def __init__(self, docs_index_name: str):
        self.RM = RecordManager_Util(docs_index_name=docs_index_name,singleton=True)

    def set_all_ids_visible(self):
        self.RM.set_field_values_for_all_ids('plot_code', 1)
        self.RM.set_field_values_for_all_ids('use4RAG', True)

    def set_field_values_by_id(self, ids: list, field_name: str, value):
        self.RM.set_field_values_by_ids(ids, field_name, value)

    def set_ids_to_visible(self, ids: list):
        self.RM.set_field_values_by_ids(ids, 'plot_code', 1)

    def set_ids_no_rag(self, ids: list):
        self.RM.set_field_values_by_ids(ids, 'use4RAG', False)

    def set_ids_yes_rag(self, ids: list):
        self.RM.set_field_values_by_ids(ids, 'use4RAG', True)

    def set_ALL_ids_yes_rag(self):
        self.RM.set_field_values_for_all_ids('use4RAG', True)

    def set_ids_to_nonvisible(self, ids: list):
        self.RM.set_field_values_by_ids(ids, 'plot_code', 0)

    def get_filtered_data(self, field_name: str, value, fields: list):
        return self.RM.get_filtered_data(field_name, value, fields)
    
    def get_filtered_by_plot_code(self, plot_code, returned_fields: list):
        # return self.RM.get_filtered_data('plot_code', plot_code, returned_fields)
        return self.RM.get_filtered_data(['plot_code','use4RAG'], [plot_code, True], returned_fields)
        
    def get_all_field_names(self):
        return self.RM.get_property_keys('name')
    
    def close_client(self):
        return self.RM.close_weaviate_client()
    
    def get_last_update(self):
        return self.RM.get_last_update_to_collection()
    
    def get_collection_schema(self):
        return self.RM.get_collection_schema()
    
    def get_collection_names(self):
        return self.RM.get_all_collection_names()
       
    def _check_valid_fields(self, fields):
        return self.RM._check_valid_fields(fields)
    
    def add_new_field(self, field, type, value):
        return self.RM.add_new_field(field, type, value)

    def get_field_values(self, fields):
        return self.RM.get_field_values(fields) 
    
    def reset_plot_field_values(self,field_name,value):
        return self.RM.set_field_values_for_all_ids(field_name,value)
    
    def set_all_values_per_filename(self,filename,field,value):
        uuid = self.RM.get_filtered_data('filename', filename, 'uuid')
        return self.RM.set_field_values_by_ids(uuid, field, value )        
    



```

```python
# plotly_project\Run_API_Server_Files.py


import subprocess
import time
import platform

def run_api_server(python_script: str):
    try:
        if platform.system() == 'Windows':
            # Using start command to open a new terminal and run poetry to start the script
            subprocess.Popen(['start', 'cmd', '/k', f'poetry run python {python_script}'], shell=True)
        else:
            # For Unix-like systems (Linux, macOS), use appropriate terminal command
            subprocess.Popen(['gnome-terminal', '--', 'poetry', 'run', 'python', python_script])

        print("API server started in a new terminal.")
    except Exception as e:
        print(f"Failed to start API server: {e}")

if __name__ == "__main__":
    script_path = '.\\plotly_project\\api_server.py'
    run_api_server(script_path)
```

```python
# plotly_project\Run_API_Server_Files_weaviate.py


import subprocess
import time
import platform

def run_api_server(python_script: str):
    try:
        if platform.system() == 'Windows':
            # Using start command to open a new terminal and run poetry to start the script
            subprocess.Popen(['start', 'cmd', '/k', f'poetry run python {python_script}'], shell=True)
        else:
            # For Unix-like systems (Linux, macOS), use appropriate terminal command
            subprocess.Popen(['gnome-terminal', '--', 'poetry', 'run', 'python', python_script])

        print("API server started in a new terminal.")
    except Exception as e:
        print(f"Failed to start API server: {e}")

if __name__ == "__main__":
    script_path = '.\\plotly_project\\api_server_weaviate.py'
    run_api_server(script_path)
```

```python
# plotly_project\server.py

from threading import Event
import uvicorn
import threading

class Server:
    def __init__(self):
        self.stop_event = Event()

    def run(self, app, port):
        config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info", reload=True)
        server = uvicorn.Server(config)

        thread = threading.Thread(target=server.run)
        thread.start()

        self.thread = thread
        self.server = server

    def stop(self):
        self.server.should_exit = True
        self.thread.join()
```

```python
# plotly_project\SQLite_Utils.py

import sqlite3
from typing import List, Tuple, Any

class SQLiteDBHandler:
    def __init__(self, db_file: str):
        """Initialize the database connection."""
        self.conn = sqlite3.connect(db_file)
        self.cursor = self.conn.cursor()

    def create_table(self, table_name: str, columns: List[Tuple[str, str]]):
        """Create a new table in the database."""
        columns_with_types = ", ".join([f"{name} {data_type}" for name, data_type in columns])
        query = f"CREATE TABLE IF NOT EXISTS {table_name} ({columns_with_types})"
        self.cursor.execute(query)
        self.conn.commit()

    def add_data(self, table_name: str, data: Tuple[Any, ...]):
        """Insert data into the specified table."""
        placeholders = ", ".join(["?"] * len(data))
        query = f"INSERT INTO {table_name} VALUES ({placeholders})"
        self.cursor.execute(query, data)
        self.conn.commit()

    def get_data(self, table_name: str, columns: List[str], where_clause: str = "", params: Tuple = ()):
        """Retrieve data from the specified table."""
        columns_str = ", ".join(columns)
        query = f"SELECT {columns_str} FROM {table_name} {where_clause}"
        self.cursor.execute(query, params)
        return self.cursor.fetchall()

    def update_data(self, table_name: str, set_clause: str, where_clause: str = "", params: Tuple = ()):
        """Update data in the specified table."""
        query = f"UPDATE {table_name} SET {set_clause} {where_clause}"
        self.cursor.execute(query, params)
        self.conn.commit()

    def delete_data(self, table_name: str, where_clause: str = "", params: Tuple = ()):
        """Delete data from the specified table."""
        query = f"DELETE FROM {table_name} {where_clause}"
        self.cursor.execute(query, params)
        self.conn.commit()

    def add_field(self, table_name: str, fields: List[Tuple[str, str]]):
        """Add a single field or list of fields to a specified table."""
        for field_name, field_type in fields:
            query = f"ALTER TABLE {table_name} ADD COLUMN {field_name} {field_type}"
            self.cursor.execute(query)
        self.conn.commit()

    def remove_field(self, table_name: str, fields: List[str]):
        """Remove a single field or list of fields from a specified table."""
        # SQLite does not support dropping columns directly. We need to create a new table without the specified fields,
        # copy data from the old table, and then replace the old table with the new one.
        existing_columns_query = f"PRAGMA table_info({table_name})"
        self.cursor.execute(existing_columns_query)
        columns_info = self.cursor.fetchall()
        existing_columns = [info[1] for info in columns_info if info[1] not in fields]
        existing_columns_str = ", ".join(existing_columns)

        temp_table_name = f"{table_name}_temp"
        create_temp_table_query = f"CREATE TABLE {temp_table_name} AS SELECT {existing_columns_str} FROM {table_name}"
        self.cursor.execute(create_temp_table_query)
        
        drop_table_query = f"DROP TABLE {table_name}"
        self.cursor.execute(drop_table_query)
        
        rename_temp_table_query = f"ALTER TABLE {temp_table_name} RENAME TO {table_name}"
        self.cursor.execute(rename_temp_table_query)
        
        self.conn.commit()

    def __del__(self):
        """Close the database connection when the object is deleted."""
        self.conn.close()

def test_sqlite_db_handler():
    db = SQLiteDBHandler('test_example.db')
    
    # Define table schema
    columns = [
        ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
        ("text", "TEXT"),
        ("metadata", "TEXT"),
        ("parameters", "TEXT")
    ]
    
    # Create a new table
    db.create_table("elements", columns)
    
    # Add data to the table without setting the id
    db.add_data("elements", (None, 'Some large text', '{"key": "value"}', '{"param": "value"}'))
    db.add_data("elements", (None, 'Another text', '{"another_key": "another_value"}', '{"another_param": "another_value"}'))
    
    # Retrieve data from the table
    data = db.get_data("elements", ["id", "text", "metadata", "parameters"])
    print("Retrieved Data:", data)
    
    # Update data in the table
    db.update_data("elements", "text = 'Updated text'", "WHERE id = ?", (1,))
    
    # Retrieve data again to check update
    updated_data = db.get_data("elements", ["id", "text", "metadata", "parameters"], "WHERE id = ?", (1,))
    print("Updated Data:", updated_data)
    
    # Add new fields to the table
    db.add_field("elements", [("new_field1", "TEXT"), ("new_field2", "INTEGER")])
    
    # Insert data with new fields
    db.add_data("elements", (None, 'New text', '{"new_key": "new_value"}', '{"new_param": "new_value"}', 'extra_text', 123))
    
    # Retrieve data to check new fields
    new_data = db.get_data("elements", ["id", "text", "metadata", "parameters", "new_field1", "new_field2"])
    print("Data with New Fields:", new_data)
    
    # Remove fields from the table
    db.remove_field("elements", ["new_field1", "new_field2"])
    
    # Retrieve data to check removal of fields
    final_data = db.get_data("elements", ["id", "text", "metadata", "parameters"])
    print("Final Data after Removing Fields:", final_data)
    
    # Delete data from the table
    db.delete_data("elements", "WHERE id = ?", (1,))
    
    # Retrieve data again to check deletion
    final_data_after_deletion = db.get_data("elements", ["id", "text", "metadata", "parameters"])
    print("Final Data after Deletion:", final_data_after_deletion)

if __name__ == "__main__":
    test_sqlite_db_handler()



```

```python
# plotly_project\static_files.py

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import logging
import os
from config import load_config

logger = logging.getLogger(__name__)
config = load_config()

def setup_static_files(app: FastAPI, static_directory: Path):
    app.mount("/static", StaticFiles(directory=static_directory, html=True), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def serve_index(request: Request):
        try:
            with open(config['index_html_path'], "r", encoding="utf-8") as file:
                html_content = file.read()
                html_content = html_content.replace("const port = 8025;", f"const port = {config['CLUSTER_BACKEND_PORT']};")
            return HTMLResponse(content=html_content, status_code=200)
        except Exception as e:
            logger.error(f"Error loading index.html: {e}")
            return HTMLResponse(content=f"Error loading index.html: {e}", status_code=500)

    @app.get(f"/{config['browser2_html']}", response_class=HTMLResponse)
    async def serve_browser2(request: Request):
        try:
            with open(config['browser2_html_path'], "r", encoding="utf-8") as file:
                html_content = file.read()
            return HTMLResponse(content=html_content, status_code=200)
        except Exception as e:
            logger.error(f"Error loading browser2.html: {e}")
            return HTMLResponse(content=f"Error loading browser2.html: {e}", status_code=500)
        
    @app.get(f"/{config['browser3_html']}", response_class=HTMLResponse)
    async def serve_browser3(request: Request):
        try:
            with open(config['browser3_html_path'], "r", encoding="utf-8") as file:
                html_content = file.read()
            return HTMLResponse(content=html_content, status_code=200)
        except Exception as e:
            logger.error(f"Error loading browser3.html: {e}")
            return HTMLResponse(content=f"Error loading browser3.html: {e}", status_code=500)
        
    @app.get(f"/{config['weaviateui_html']}", response_class=HTMLResponse)
    async def serve_browser2(request: Request):
        try:
            with open(config['weaviateui_html_path'], "r", encoding="utf-8") as file:
                html_content = file.read()
            return HTMLResponse(content=html_content, status_code=200)
        except Exception as e:
            logger.error(f"Error loading weaviateui.html: {e}")
            return HTMLResponse(content=f"Error loading weaviateui.html: {e}", status_code=500)

    # Serve the favicon
    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return FileResponse(static_directory / "favicon.ico")

```

```python
# plotly_project\Test_openai_embedding_with_weaviate_hybrid_search.py

import os
from langchain_openai import AzureOpenAIEmbeddings 
import weaviate
import weaviate.classes as wvc
from weaviate.classes.init import Auth
from weaviate.classes.query import HybridFusion
import pprint


os.environ['AZURE_OPENAI_API_KEY'] = '64393fb9052e4efa8757fa0556890260'
os.environ["AZURE_OPENAI_ENDPOINT"] = 'https://oai-eng-dev-usgov-east-01.openai.azure.us/'
WEAVIATE_URL = os.environ.get("WEAVIATE_URL")
WEAVIATE_API_KEY = os.environ.get("WEAVIATE_API_KEY")
WEAVIATE_DOCS_INDEX_NAME = 'JACSKE_Program'

api_version="2024-02-01"
model4="gpt-4"
model35="gpt-35-turbo"
embedder_model = "text-embedding-ada-002"

embeddings_client = AzureOpenAIEmbeddings(
    model=embedder_model, 
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"), 
    api_key=os.getenv("AZURE_OPENAI_API_KEY"), 
    chunk_size=200, 
    api_version=api_version,
)

text = "Where is the XMIT Trig signal created"


def search_weaviate(index, query, alpha, limit = 5, query_properties= None, return_score=False, explain_score=False, fusion_type='RELATIVE_SCORE'):

    weaviate_client = client.collections.get(index)

    embedding = embeddings_client.embed_query(text)

    if fusion_type == 'RELATIVE_SCORE':
        fusion_type=HybridFusion.RELATIVE_SCORE
    elif fusion_type == 'RANKED' or fusion_type == None:
        fusion_type=HybridFusion.RANKED
    else:
        print(f"{fusion_type} is not a valid fusion setting")


    result = weaviate_client.query.hybrid(
        query=text,
        vector=embedding,
        alpha=alpha,
        return_metadata=wvc.query.MetadataQuery(score=return_score, explain_score=explain_score),
        query_properties=query_properties,#array of strings to limit the set of properties for the BM25 component of the search. If unspecified, all text properties will be searched.
        #Specific properties can be boosted by a factor specified as a number after the caret sign, for example properties: ["title^3", "summary"].
        # filters=wvc.query.Filter.by_property("wordCount").less_than(1000),
        fusion_type=fusion_type,
        # return_properties=["references"],
        limit=limit,
    )
    return result.objects




with weaviate.connect_to_local(auth_credentials=Auth.api_key(WEAVIATE_API_KEY)) as client:

    print(client.is_ready())
    weaviate_client = client.collections.get(WEAVIATE_DOCS_INDEX_NAME)

    embedding = embeddings_client.embed_query(text)

    result = search_weaviate(
        WEAVIATE_DOCS_INDEX_NAME,
        text,
        alpha = .75, 
        limit = 30, 
        query_properties= None, 
        return_score=True, 
        explain_score=False, 
        fusion_type='RELATIVE_SCORE'
    )

 
    for o in result:
        pprint.pprint(o.properties['page_content'])
        print(o.metadata.score)
        print(o.metadata.explain_score)
        print("*********************")





```

```python
# plotly_project\test_server.py

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


```

```python
# plotly_project\Update_Weaviate.py

import weaviate
import os
import json
from contextlib import contextmanager
from weaviate.auth import AuthApiKey

def get_weaviate_ids_from_field_values(client, index, field, value) -> list[str]:
    try:
        value = json.dumps(value)[1:-1]  # Remove the quotes added by json.dumps
        # Query to get objects with fields values equal to value
        def get_query(field: str, value: str, index: str) -> str:
            return f"""
{{
Get {{
    {index}(
    where: {{
        path: ["{field}"],
        operator: Equal,
        valueText: "{value}"
    }}
    ) {{
    _additional {{ id }}
    acronym_list
    }}
}}
}}
"""
        query = get_query(field, value, index)
        response = client.query.raw(query)

        results = []
        for rsp in response['data']['Get'][index]:
            results.append(rsp['_additional']['id'])

        if results:      
            return results
        return None
    
    except KeyError as e:
        print(f"KeyError: {e}")
        return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def update_weaviate_field_values(client, index, ids, field, value):
    try:
        if ids:
            if not isinstance(ids, list):
                ids = [ids]

            value = json.dumps(value)[1:-1] 

            for id in ids:
                client.data_object.update(
                    data_object={field: value},
                    class_name=index,
                    uuid=id
                )
            return ids
        else:
            print("No elements found that match the filtered criteria")
            return None
    except Exception as e:
        print(f"An error occurred while updating: {e}")

# Context manager for Weaviate client
@contextmanager
def weaviate_client(WEAVIATE_URL, WEAVIATE_API_KEY):
    client = weaviate.Client(
        url=WEAVIATE_URL,
        auth_client_secret=AuthApiKey(api_key=WEAVIATE_API_KEY),
    )
    try:
        yield client
    finally:
        # Explicitly close the HTTP session
        client._connection.close()



def _replace_weaviate_field_values(client, index, filter_field, filter_value, update_field, update_value):
    # Example usage
    ids = get_weaviate_ids_from_field_values(
        client, 
        index, 
        filter_field, 
        filter_value
    )
    # Update field values for example IDs
    ids = update_weaviate_field_values(
        client, 
        index, 
        ids, 
        update_field, 
        update_value
    )
    return ids

def replace_weaviate_field_values(index, filter_field, filter_value, update_field, update_value,client=None, url=None, key=None):
    if not client:
        with weaviate_client(WEAVIATE_URL, WEAVIATE_API_KEY) as client:
            return _replace_weaviate_field_values(
                client, 
                index, 
                filter_field, 
                filter_value, 
                update_field,
                update_value,
            )
    else:
        return _replace_weaviate_field_values(
            client, 
            index, 
            filter_field, 
            filter_value, 
            update_field,
            update_value,
        )

if __name__ == "__main__":
    WEAVIATE_URL = os.environ.get("WEAVIATE_URL")
    WEAVIATE_API_KEY = os.environ.get("WEAVIATE_API_KEY")
    WEAVIATE_DOCS_INDEX_NAME = 'SEPs_F_T_C_W_A_V' 
    filter_field = "file_path"
    filter_value = "\\home.drs.com@ssl\\DavWWWRoot\\business03\\home\\SEPs\\SEP-17 Business Development\\SEP-17-08(I) Color Teams Guidelines.docx"
    update_field = filter_field#"acronym_list"
    test_list = ["The first", "the second", "the third"]
    update_value = filter_value#f"{test_list}"

    # filter_field = "acronym_list"
    # filter_value = f"""["The first", "the second", "the third"]"""
    
    ids = replace_weaviate_field_values(
        index=WEAVIATE_DOCS_INDEX_NAME, 
        filter_field=filter_field, 
        filter_value=filter_value, 
        update_field=update_field, 
        update_value=update_value,
        url=WEAVIATE_URL, 
        key=WEAVIATE_DOCS_INDEX_NAME
    )

    print(ids)
```

```html
<!-- plotly_project\static\browser2.html -->

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Selected Embeddings</title>
    <link rel="stylesheet" href="/static/style2.css">
</head>
<body>
    <h1>Selected Embeddings</h1>
    <button id="config_table_btn">Config Table</button>
    <br>
    <a href="#" id="removeFromRAGSearch">Remove From RAG Search</a>
    <br>
    <a href="#" id="add_back_plot">Add back to plot</a>
    <table id="embeddings_table">
        <thead>
            <tr id="table_headers">
                <th><input type="checkbox" id="select_all"></th>
                <th>UUID <button class="sort-btn" onclick="sortTable('uuid')"></button></th>
                <th>Filename <button class="sort-btn" onclick="sortTable('filename')"></button></th>
                <th>Content <button class="sort-btn" onclick="sortTable('page_content')"></button></th>
            </tr>
        </thead>
        <tbody>
        </tbody>
    </table>
    <div id="myModal" class="modal">
        <div class="modal-content">
            <span class="close">&times;</span>
            <pre id="modalText" style="white-space: pre-wrap; word-wrap: break-word;"></pre>
        </div>
    </div>
    <div id="configModal" class="modal">
        <div class="modal-content">
            <span class="close-config">&times;</span>
            <table id="config_table">
                <thead>
                    <tr>
                        <th>Fields</th>
                        <th>Select</th>
                    </tr>
                </thead>
                <tbody>
                </tbody>
            </table>
            <button id="select_all_btn">Select All</button>
            <button id="deselect_all_btn">Deselect All</button>
            <button id="apply_config_btn">Accept</button>
            <button id="cancel_config_btn">Cancel</button>
        </div>
    </div>
    <script src="/static/script2.js"></script>
</body>
</html>

```

```html
<!-- plotly_project\static\browser2_0.html -->

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Selected Embeddings</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #f4f4f4;
            margin: 0;
            padding: 20px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }
        table, th, td {
            border: 1px solid #ddd;
        }
        th, td {
            padding: 8px;
            text-align: left;
            max-width: 150px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        th {
            background-color: #f2f2f2;
        }
        .modal {
            display: none;
            position: fixed;
            z-index: 1;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            overflow: auto;
            background-color: rgb(0,0,0);
            background-color: rgba(0,0,0,0.4);
        }
        .modal-content {
            background-color: #fefefe;
            margin: 15% auto;
            padding: 20px;
            border: 1px solid #888;
            width: 80%;
            max-height: 70%;
            overflow-y: auto;
        }
        .close {
            color: #aaa;
            float: right;
            font-size: 28px;
            font-weight: bold;
        }
        .close:hover,
        .close:focus {
            color: black;
            text-decoration: none;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <h1>Selected Embeddings</h1>
    <table id="embeddings_table">
        <thead>
            <tr>
                <th></th>
                <th>ID</th>
                <th>Filename</th>
                <th>Content</th>
            </tr>
        </thead>
        <tbody>
        </tbody>
    </table>
    <div id="myModal" class="modal">
        <div class="modal-content">
            <span class="close">&times;</span>
            <pre id="modalText" style="white-space: pre-wrap; word-wrap: break-word;"></pre>
        </div>
    </div>
    <script>
        async function loadSelectedEmbeddings() {
            try {
                const response = await fetch('/data/selected_embeddings.json');
                if (!response.ok) {
                    throw new Error(`Error fetching data: ${response.statusText}`);
                }
                const data = await response.json();
                const tableBody = document.getElementById('embeddings_table').getElementsByTagName('tbody')[0];

                // Clear any existing rows
                tableBody.innerHTML = '';

                // Add new rows with numbering
                data.forEach((item, index) => {
                    const row = document.createElement('tr');
                    const cellNumber = document.createElement('td');
                    const cellID = document.createElement('td');
                    const cellFilename = document.createElement('td');
                    const cellContent = document.createElement('td');
                    const cellView = document.createElement('td');

                    cellNumber.textContent = index + 1;
                    cellID.textContent = item.id || 'N/A';
                    cellFilename.textContent = item.filename || 'N/A';
                    cellContent.textContent = item.content.substring(0, 30) + '...';
                    cellView.innerHTML = `<span class="view-btn" style="cursor:pointer; color:blue;">[View]</span>`;
                    cellView.addEventListener('click', () => {
                        document.getElementById('modalText').textContent = item.content;
                        document.getElementById('myModal').style.display = "block";
                    });

                    row.appendChild(cellNumber);
                    row.appendChild(cellID);
                    row.appendChild(cellFilename);
                    row.appendChild(cellContent);
                    row.appendChild(cellView);
                    tableBody.appendChild(row);
                });
            } catch (error) {
                console.error('Error loading selected embeddings:', error);
            }
        }

        // Get the modal
        const modal = document.getElementById("myModal");

        // Get the <span> element that closes the modal
        const span = document.getElementsByClassName("close")[0];

        // When the user clicks on <span> (x), close the modal
        span.onclick = function() {
            modal.style.display = "none";
        }

        // When the user clicks anywhere outside of the modal, close it
        window.onclick = function(event) {
            if (event.target == modal) {
                modal.style.display = "none";
            }
        }

        // Load selected embeddings every 5 seconds
        setInterval(loadSelectedEmbeddings, 5000);
        window.onload = loadSelectedEmbeddings;
    </script>
</body>
</html>

```

```html
<!-- plotly_project\static\browser3.html -->

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Selected Embeddings</title>
    <link rel="stylesheet" href="/static/style3.css">
</head>
<body>
    <h1>Selected Embeddings</h1>
    <button id="config_table_btn">Config Table</button>
    <br>
    <a href="#" id="removeFromRAGSearch">Remove From RAG Search</a>
    <br>
    <a href="#" id="add_back_plot">Add back to plot</a>
    <table id="embeddings_table">
        <thead>
            <tr id="table_headers">
                <th><input type="checkbox" id="select_all"></th>
                <th>UUID <button class="sort-btn" onclick="sortTable('uuid')"></button></th>
                <th>Filename <button class="sort-btn" onclick="sortTable('filename')"></button></th>
                <th>Content <button class="sort-btn" onclick="sortTable('page_content')"></button></th>
            </tr>
        </thead>
        <tbody>
        </tbody>
    </table>
    <div id="myModal" class="modal">
        <div class="modal-content">
            <span class="close">&times;</span>
            <pre id="modalText" style="white-space: pre-wrap; word-wrap: break-word;"></pre>
        </div>
    </div>
    <div id="configModal" class="modal">
        <div class="modal-content">
            <span class="close-config">&times;</span>
            <table id="config_table">
                <thead>
                    <tr>
                        <th>Fields</th>
                        <th>Select</th>
                    </tr>
                </thead>
                <tbody>
                </tbody>
            </table>
            <button id="select_all_btn">Select All</button>
            <button id="deselect_all_btn">Deselect All</button>
            <button id="apply_config_btn">Accept</button>
            <button id="cancel_config_btn">Cancel</button>
        </div>
    </div>
    <script src="/static/script3.js"></script>
</body>
</html>

```

```html
<!-- plotly_project\static\index.html -->

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Centered Plotly Plots</title>
    <link rel="stylesheet" href="/static/style.css">
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
</head>
<body>
    <!-- This container is shown during database status check -->
    <div id="status-container">
        <h1 id="status-message" class="error-message">Checking database status...</h1>
        <button id="init-database-btn" class="hidden">Initialize Database</button>
    </div>
    
    <!-- Main content is hidden initially -->
    <div id="main-content" class="hidden">
        <div class="control-container">
            <div class="dropdown-container">
                <select id="plot-select" onchange="handlePlotSelection()">
                    <option value="plot_type" disabled selected>Select Plot</option>
                    <option value="scatter">Scatter</option>
                    <option value="bar">Bar</option>
                    <option value="centroid">Cluster</option>
                </select>
            </div>
            <div class="dropdown-container">
                <select id="operation-select" onchange="handleOperationSelection()">
                    <option value="operations" disabled selected>Operations</option>
                    <option value="delete_cluster">Delete Cluster</option>
                    <option value="delete_embedding">Delete Embedding</option>
                    <option value="process_acronyms">Process Acronyms</option>
                    <option value="recalc_clusters">Recalc Clusters</option>
                    <option value="remove_from_rag">Do Not Include in RAG Search</option>
                </select>
            </div>
            <div class="button-container">
                <button id="Reset_embeddings_btn">Reset Embeddings</button>
            </div>
            <div class="dropdown-container">
                <select id="collection-select" onchange="handleCollectionSelection()">
                    <!-- Options will be populated dynamically -->
                </select>
            </div>
        </div>
        <div class="plots-wrapper">
            <div class="plot-container" id="scatter_plot"></div>
            <div class="plot-container" id="bar_plot"></div>
            <div class="plot-container" id="centroid_plot"></div>
        </div>
    </div>
    <script src="/static/script.js"></script>
</body>
</html>

```

```html
<!-- plotly_project\static\index0.html -->

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Centered Plotly Plots</title>
    <style>
        body {
            display: flex;  /* Sets the body to use flexbox layout */
            justify-content: flex-start;  /* Aligns content to the start vertically */
            align-items: center;  /* Centers content horizontally */
            flex-direction: column;  /* Stacks content in a column */
            min-height: 100vh;  /* Ensures the body takes up at least the full viewport height */
            margin: 0;  /* Removes default margin */
            padding: 20px;  /* Adds padding to the body */
            background-color: #f4f4f4;  /* Optional: Background color for better visualization */
        }
        .plot-container {
            width: 100%;  /* Makes the container take the full width of its parent */
            max-width: 800px;  /* Sets a maximum width for the container */
            padding: 20px;  /* Adds padding inside the container */
            background-color: white;  /* Optional: Background color for the plot container */
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);  /* Optional: Box shadow for better appearance */
            margin-bottom: 20px;  /* Adds space below each container */
            text-align: center;  /* Center-aligns the text inside the container */
            display: flex;  /* Sets the container to use flexbox layout */
            justify-content: center;  /* Centers plot content horizontally */
            align-items: center;  /* Centers plot content vertically */
            z-index: 1; /* Lower z-index for plot container */
        }
        .plots-wrapper {
            display: flex;  /* Sets the wrapper to use flexbox layout */
            flex-direction: column;  /* Stacks content in a column */
            align-items: center;  /* Centers content horizontally */
            justify-content: flex-start;  /* Aligns content to the start vertically */
            width: 100%;  /* Makes the wrapper take the full width of its parent */
        }
        .button-container {
            margin-top: 20px;
            margin-bottom: 20px; /* Adds space below the buttons */
            display: flex;
            justify-content: center;
            gap: 10px;
            z-index: 2;  /* Ensure the buttons are on top */
            position: relative; /* Ensure the buttons are positioned correctly */
        }
        button {
            padding: 10px 20px;
            font-size: 16px;
        }
    </style>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
</head>
<body>
    <!-- Buttons for interactive actions -->
    <div class="button-container">
        <button id="delete_cluster_btn">Delete Cluster</button>
        <button id="delete_embedding_btn">Delete Embedding</button>
        <button id="process_acronyms_btn">Process Acronyms</button>
        <button id="clear_selected_embeddings_btn">Clear Selected Embeddings</button>
    </div>
    <div class="plots-wrapper">
        <div class="plot-container">
            <!-- Insert Scatter Plot here -->
            <div id="scatter_plot"></div>
        </div>
        <div class="plot-container">
            <!-- Insert Bar Plot here -->
            <div id="bar_plot"></div>
        </div>
        <div class="plot-container">
            <!-- Insert Centroid Plot here -->
            <div id="centroid_plot"></div>
        </div>
    </div>
    <script>
        const port = 8025; // Define the port variable here

        // Initialize selected cluster and embedding
        window.selectedCluster = undefined;
        window.selectedEmbedding = undefined;

        async function loadJSON(url) {
            try {
                const response = await fetch(url);
                if (!response.ok) throw new Error(`Error loading ${url}: ${response.statusText}`);
                return await response.json();
            } catch (error) {
                console.error(error);
                alert(`Failed to load data from ${url}`);
            }
        }

        async function createScatterPlot() {
            // Construct the URL to fetch from the correct endpoint
            const data = await loadJSON('/data/scatter_plot_data.json');
            if (!data) return;

            const traces = [];
            const clusters = Array.from(new Set(data.map(d => d.cluster)));

            clusters.forEach(cluster => {
                const clusterData = data.filter(d => d.cluster === cluster);
                traces.push({
                    x: clusterData.map(d => d.tsne1),
                    y: clusterData.map(d => d.tsne2),
                    mode: 'markers',
                    type: 'scatter',
                    name: `Cluster ${cluster}`,
                    text: clusterData.map(d => `Cluster: ${d.cluster}<br>Filename: ${d.filename}<br>Content: ${d.content.substring(0, 80)}<br>ID: ${d.id}`),
                    marker: { size: 10 }
                });
            });

            const layout = {
                title: 't-SNE Clustering of Documents',
                dragmode: 'lasso',
                hovermode: 'closest',  // Set the default hover mode to 'closest'
                updatemenus: [{
                    buttons: clusters.map(cluster => ({
                        method: 'update',
                        label: `Cluster ${cluster}`,
                        args: [{'visible': clusters.map(c => c === cluster)}, {}]
                    })).concat([{
                        method: 'update',
                        label: 'All',
                        args: [{'visible': clusters.map(() => true)}, {}]
                    }]),
                    direction: 'down',
                    showactive: true
                }]
            };

            Plotly.newPlot('scatter_plot', traces, layout);

            const scatterPlot = document.getElementById('scatter_plot');
            scatterPlot.on('plotly_selected', function(eventData) {
                const selectedPoints = eventData.points.map(point => {
                    return {
                        tsne1: point.x,
                        tsne2: point.y,
                        filename: point.text.split('<br>')[1].split(': ')[1],
                        content: point.text.split('<br>')[2].split(': ')[1],
                        id: point.text.split('<br>')[3].split(': ')[1]
                    };
                });

                console.log('Sending selected embeddings:', selectedPoints);

                fetch(`http://localhost:${port}/selected_embeddings`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(selectedPoints)
                })
                .then(response => response.json())
                .then(data => {
                    console.log('Selected embeddings sent successfully:', data);
                    reloadScatterPlot(); // Reload the scatter plot after saving embeddings
                })
                .catch(error => {
                    console.error('Error sending selected embeddings:', error);
                    alert('Failed to send selected embeddings');
                });
            });
        }

        async function createBarPlot() {
            const data = await loadJSON('/data/bar_plot_data.json');
            if (!data) return;

            const trace = {
                x: data.x,
                y: data.y,
                type: 'bar'
            };

            const layout = {
                title: 'Cluster Distribution',
                xaxis: { title: 'Cluster' },
                yaxis: { title: 'Number of Documents' }
            };

            Plotly.newPlot('bar_plot', [trace], layout);
        }

        async function createCentroidPlot() {
            const data = await loadJSON('/data/centroid_plot_data.json');
            if (!data) return;

            const trace = {
                x: data.map(d => d.tsne1),
                y: data.map(d => d.tsne2),
                mode: 'markers',
                type: 'scatter',
                marker: { color: data.map(d => d.cluster) }
            };

            const layout = {
                title: 't-SNE Visualization of Cluster Centroids',
                xaxis: { title: 't-SNE 1' },
                yaxis: { title: 't-SNE 2' }
            };

            Plotly.newPlot('centroid_plot', [trace], layout);
        }

        async function reloadScatterPlot() {
            // Clear the existing scatter plot
            Plotly.purge('scatter_plot');
            // Recreate the scatter plot
            await createScatterPlot();
        }

        window.onload = function() {
            createScatterPlot();
            createBarPlot();
            createCentroidPlot();
        };

        document.getElementById('delete_cluster_btn').addEventListener('click', () => {
            if (window.selectedCluster !== undefined) {
                fetch(`/clusters/${window.selectedCluster}`, { method: 'DELETE' })
                    .then(response => response.json())
                    .then(data => {
                        console.log(data);
                        alert('Cluster deleted successfully');
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        alert('Failed to delete cluster');
                    });
            } else {
                alert('No cluster selected.');
            }
        });

        document.getElementById('delete_embedding_btn').addEventListener('click', () => {
            if (window.selectedEmbedding !== undefined) {
                fetch(`/embeddings/${window.selectedEmbedding}`, { method: 'DELETE' })
                    .then(response => response.json())
                    .then(data => {
                        console.log(data);
                        alert('Embedding deleted successfully');
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        alert('Failed to delete embedding');
                    });
            } else {
                alert('No embedding selected.');
            }
        });

        document.getElementById('process_acronyms_btn').addEventListener('click', () => {
            if (window.selectedCluster !== undefined) {
                fetch(`/process_acronyms/${window.selectedCluster}`, { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        console.log(data);
                        alert('Acronyms processed successfully');
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        alert('Failed to process acronyms');
                    });
            } else {
                alert('No cluster selected.');
            }
        });

        document.getElementById('clear_selected_embeddings_btn').addEventListener('click', () => {
            fetch('/clear_selected_embeddings', { method: 'DELETE' })
                .then(response => response.json())
                .then(data => {
                    console.log(data);
                    alert('Selected embeddings cleared successfully');
                    reloadScatterPlot(); // Reload the scatter plot after clearing embeddings
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Failed to clear selected embeddings');
                });
        });
    </script>
</body>
</html>

```

```javascript
// plotly_project\static\script.js

let port;

async function getConfig() {
    const response = await fetch('/config');
    const config = await response.json();
    port = config.port;
    await populateCollectionDropdown(); // Populate the collection dropdown
    checkDatabaseInitStatus(); // Start checking the database status after fetching the config
}

async function checkDatabaseInitStatus() {
    try {
        const response = await fetch('http://localhost:8025/check_database_init_status');
        const data = await response.json();

        if (data.status === 'OK') {
            document.getElementById('status-container').classList.add('hidden');
            document.getElementById('main-content').classList.remove('hidden');
            document.getElementById('main-content').style.display = 'block'; // Ensure main content is shown
            initializeApplication();
        } else {
            displayNotInitializedMessage();
            setTimeout(checkDatabaseInitStatus, 5000); // Retry every 5 seconds if not initialized
        }
    } catch (error) {
        console.error('Error checking database status:', error);
        setTimeout(checkDatabaseInitStatus, 5000); // Retry every 5 seconds in case of error
    }
}

function displayNotInitializedMessage() {
    const statusMessage = document.getElementById('status-message');
    const initDatabaseBtn = document.getElementById('init-database-btn');

    statusMessage.textContent = 'Database Is Not Initialized for Post-Processing';
    initDatabaseBtn.classList.remove('hidden');
    initDatabaseBtn.onclick = initializeDatabase;
}

async function initializeDatabase() {
    try {
        const response = await fetch('http://localhost:8025/initialize_database');
        const data = await response.json();

        if (data.status === 'Done') {
            checkDatabaseInitStatus(); // Trigger a status check after initialization
        } else {
            console.error('Database initialization failed:', data);
        }
    } catch (error) {
        console.error('Error initializing database:', error);
    }
}

function initializeApplication() {
    console.log("Configured port:", port);
    // Clear existing plots
    Plotly.purge('scatter_plot');
    Plotly.purge('bar_plot');
    Plotly.purge('centroid_plot');

    createPlot('scatter_plot', '/plotV1/scatter_plot/visible', plotScatter);
    createPlot('bar_plot', '/plotV1/bar_plot/visible', plotBar);
    createPlot('centroid_plot', '/plotV1/centroid_plot/visible', plotCentroid);

    const clearButton = document.getElementById('Reset_embeddings_btn');
    clearButton.addEventListener('click', async function() {
        try {
            const response = await fetch(`/plotV1/show_all_plot_data`, { method: 'GET' });
            if (response.ok) {
                const data = await response.json();
                console.log('Selected embeddings cleared successfully:', data);
                reloadScatterPlot();
            } else {
                throw new Error(`Failed to clear selected embeddings: ${response.statusText}`);
            }
        } catch (error) {
            console.error('Error clearing selected embeddings:', error);
            alert('Failed to clear selected embeddings');
        }
    });

    updatePlotVisibility('scatter');
    window.addEventListener('resize', resizePlots);
}

async function fetchPlotData(endpoint) {
    try {
        const response = await fetch(endpoint);
        if (!response.ok) throw new Error(`Error loading ${endpoint}: ${response.statusText}`);
        return await response.json();
    } catch (error) {
        console.error(error);
        alert(`Failed to load data from ${endpoint}`);
    }
}

async function createPlot(containerId, endpoint, plotFunction) {
    const data = await fetchPlotData(endpoint);
    if (data) plotFunction(data, containerId);
}

function plotScatter(data, containerId) {
    console.log('Plotting Scatter Plot in', containerId);

    const traces = [];
    const clusters = Array.from(new Set(data.map(d => d.clusterID)));
    console.log('Clusters found:', clusters); // Log clusters

    clusters.forEach(clusterID => {
        console.log('Data received for plotting:', data);
        const clusterData = data.filter(d => d.clusterID === clusterID);
        console.log('UUIDs for this cluster:', clusterData.map(d => d.uuid)); // Check UUIDs

        traces.push({
            x: clusterData.map(d => d.tsne_x),
            y: clusterData.map(d => d.tsne_y),
            mode: 'markers',
            type: 'scatter',
            name: `Cluster ${clusterID}`,
            text: clusterData.map(d => `Cluster: ${d.clusterID}<br>Filename: ${d.filename}<br>Content: ${d.page_content.substring(0, 80)}<br>UUID: ${d.uuid}`),
            customdata: clusterData.map(d => d.uuid), // Include the id in customdata
            marker: { size: 10 }
        });
    });

    console.log('Traces created:', traces); // Log traces

    const layout = {
        title: 't-SNE Clustering of Documents',
        dragmode: 'lasso',
        hovermode: 'closest'
    };

    Plotly.newPlot(containerId, traces, layout);

    const scatterPlot = document.getElementById(containerId);
    scatterPlot.on('plotly_selected', function(eventData) {
        const selectedPoints = eventData.points.map(point => point.customdata);
    
        console.log('Selected Points:', selectedPoints); // Log selected points before sending
    
        fetch(`/plotV1/remove_points`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ selected_ids: selectedPoints })
        })
        .then(response => response.json())
        .then(data => {
            console.log('Selected embeddings sent successfully:', data);
            reloadScatterPlot(); // Reload the scatter plot after saving embeddings
        })
        .catch(error => {
            console.error('Error sending selected embeddings:', error);
            alert('Failed to send selected embeddings');
        });
    });
}

function plotBar(data, containerId) {
    const trace = {
        x: data.x,
        y: data.y,
        type: 'bar'
    };

    const layout = {
        title: 'Cluster Distribution',
        xaxis: { title: 'Cluster' },
        yaxis: { title: 'Number of Documents' }
    };

    Plotly.newPlot(containerId, [trace], layout);
}

function plotCentroid(data, containerId) {
    const trace = {
        x: data.map(d => d.tsne_x),
        y: data.map(d => d.tsne_y),
        mode: 'markers',
        type: 'scatter',
        marker: { color: data.map(d => d.clusterID) }
    };

    const layout = {
        title: 't-SNE Visualization of Cluster Centroids',
        xaxis: { title: 't-SNE 1' },
        yaxis: { title: 't-SNE 2' }
    };

    Plotly.newPlot(containerId, [trace], layout);
}

function updatePlotVisibility(selectedPlot) {
    document.getElementById('scatter_plot').style.display = 'none';
    document.getElementById('bar_plot').style.display = 'none';
    document.getElementById('centroid_plot').style.display = 'none';

    if (selectedPlot === 'scatter') {
        document.getElementById('scatter_plot').style.display = 'block';
    } else if (selectedPlot === 'bar') {
        document.getElementById('bar_plot').style.display = 'block';
    } else if (selectedPlot === 'centroid') {
        document.getElementById('centroid_plot').style.display = 'block';
    }

    // Resize the visible plot
    resizePlots();
}

function handleOperationSelection() {
    const operationSelect = document.getElementById('operation-select');
    const selectedOperation = operationSelect.value;

    if (selectedOperation !== 'operations') {
        let maxClusters = null;
        let minClusters = null;


        // Check if the selected operation is related to clustering
        if (selectedOperation === 'recalc_clusters') {
            maxClusters = prompt('Enter the max number of clusters (an integer value):');
            minClusters = prompt('Enter the min number of clusters (an integer value):');
            if (maxClusters === null) {
                // If the user cancels the prompt, don't proceed with the operation
                operationSelect.value = 'operations';
                return;
            }
            if (minClusters === null) {
                // If the user cancels the prompt, don't proceed with the operation
                operationSelect.value = 'operations';
                return;
            }

            // Ensure the input is a valid integer
            maxClusters = parseInt(maxClusters, 10);
            if (isNaN(maxClusters) || maxClusters <= 0) {
                alert('Please enter a valid positive integer for the max number of clusters. Must be creater than Min Clusters');
                operationSelect.value = 'operations';
                return;
            }
            minClusters = parseInt(minClusters, 10);
            if (isNaN(minClusters) || minClusters <= 1) {
                alert('Please enter a valid positive integer for the min number of clusters. Must be greater than 2 abd less than Max Clusters');
                operationSelect.value = 'operations';
                return;
            }
        }

        const confirmed = confirm(`Are you sure you want to perform the operation: ${selectedOperation.replace('_', ' ')}?`);
        if (confirmed) {
            executeOperation(selectedOperation, maxClusters, minClusters);
        }

        // Reset to 'Operations' after selection
        operationSelect.value = 'operations';




    }
}

function handlePlotSelection() {
    const plotSelect = document.getElementById('plot-select');
    const selectedPlot = plotSelect.value;

    if (selectedPlot !== 'plot_type') {
        updatePlotVisibility(selectedPlot);

        // Reset to 'plot_type' after selection
        plotSelect.value = 'plot_type';
    }
}

async function executeOperation(operation, maxClusters = null, minClusters = null) {
    try {
        const requestData = {};
        
        // Include max_clusters in the request if provided
        if (maxClusters !== null) {
            requestData.max_clusters = maxClusters;
        }
        if (minClusters !== null) {
            requestData.min_clusters = minClusters;
        }

        const response = await fetch(`/data/operations/${operation}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });

        if (response.ok) {
            const data = await response.json();
            console.log(`${operation.replace('_', ' ')} executed successfully:`, data);
            initializeApplication()
        } else {
            throw new Error(`Failed to execute ${operation}: ${response.statusText}`);
        }
    } catch (error) {
        console.error(`Error executing ${operation}:`, error);
        alert(`Failed to execute ${operation}`);
    }
}

async function reloadScatterPlot() {
    // Clear the existing scatter plot
    Plotly.purge('scatter_plot');
    // Recreate the scatter plot
    await createPlot('scatter_plot', '/plotV1/scatter_plot/visible', plotScatter);
}

async function reloadBarPlot() {
    // Clear the existing bar plot
    Plotly.purge('bar_plot');
    // Recreate the bar plot
    await createPlot('bar_plot', '/plotV1/bar_plot/visible', plotBar);
}

async function reloadClusterPlot() {
    // Clear the existing cluster plot
    Plotly.purge('centroid_plot');
    // Recreate the cluster plot
    await createPlot('centroid_plot', '/plotV1/centroid_plot/visible', plotCentroid);
}

function resizePlots() {
    const scatterPlot = document.getElementById('scatter_plot');
    const barPlot = document.getElementById('bar_plot');
    const centroidPlot = document.getElementById('centroid_plot');

    if (scatterPlot.style.display === 'block') {
        Plotly.Plots.resize(scatterPlot);
    }
    if (barPlot.style.display === 'block') {
        Plotly.Plots.resize(barPlot);
    }
    if (centroidPlot.style.display === 'block') {
        Plotly.Plots.resize(centroidPlot);
    }
}

async function populateCollectionDropdown() {
    try {
        // Fetch collection names
        const response = await fetch('/data/schema/get_all_collection_names');
        const data = await response.json();
        const collections = data.result;
        
        // Fetch the currently selected collection
        const selectedResponse = await fetch('/data/schema/get_selected_collection');
        const selectedData = await selectedResponse.json();
        const selectedCollection = selectedData.selected_collection;
        
        const collectionSelect = document.getElementById('collection-select');
        
        // Clear existing options
        collectionSelect.innerHTML = '';
        
        // Add a default option
        const defaultOption = document.createElement('option');
        defaultOption.value = '';
        defaultOption.textContent = 'Select Collection';
        defaultOption.disabled = true;
        collectionSelect.appendChild(defaultOption);
        
        // Populate the dropdown
        collections.forEach(collection => {
            const option = document.createElement('option');
            option.value = collection;
            option.textContent = collection;
            if (collection === selectedCollection) {
                option.selected = true;
            }
            collectionSelect.appendChild(option);
        });
    } catch (error) {
        console.error('Error fetching collection names:', error);
    }
}

async function handleCollectionSelection() {
    const collectionSelect = document.getElementById('collection-select');
    const selectedCollection = collectionSelect.value;
    
    if (selectedCollection) {
        // Send the selected collection to the backend
        try {
            const response = await fetch('/data/schema/set_selected_collection', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ collection_name: selectedCollection })
            });
            
            const data = await response.json();
            if (response.ok) {
                console.log('Selected collection set successfully:', data);
                // Re-initialize the application with the new collection
                initializeApplication();
            } else {
                console.error('Error setting selected collection:', data);
            }
        } catch (error) {
            console.error('Error setting selected collection:', error);
        }
    }
}


window.onload = getConfig; // Start the configuration fetching on window load

```

```javascript
// plotly_project\static\script2.js

// script2.js
let selectedFields = ['uuid', 'filename', 'page_content']; // Default selected fields
let ascending = true; // Sort order
let currentData = []; // Store the current data for updating fields
let selectedIds = new Set(); // Store selected IDs
let isSelectAllChecked = false; // Track the state of the select_all checkbox

// Function to load selected embeddings
async function loadSelectedEmbeddings(fieldNames = selectedFields) {
    try {
        const queryString = fieldNames.map(field => `fields=${encodeURIComponent(field)}`).join('&');
        const response = await fetch(`/plotV1/scatter_plot/nonvisible?${queryString}`);
        if (!response.ok) {
            throw new Error(`Error fetching data: ${response.statusText}`);
        }
        const data = await response.json();
        currentData = data;
        updateTable();
    } catch (error) {
        console.error('Error loading selected embeddings:', error);
    }
}

// Function to update the table based on current data
function updateTable() {
    const tableBody = document.getElementById('embeddings_table').getElementsByTagName('tbody')[0];

    // Clear any existing rows
    tableBody.innerHTML = '';

    // Clear existing table headers
    const tableHeaders = document.getElementById('table_headers');
    tableHeaders.innerHTML = '<th><input type="checkbox" id="select_all"></th>';

    // Add new table headers based on selected fields
    selectedFields.forEach(field => {
        const th = document.createElement('th');
        th.innerHTML = `${field} <button class="sort-btn" onclick="sortTable('${field}')"></button>`;
        th.appendChild(createResizeHandle());
        tableHeaders.appendChild(th);
    });

    // Add new rows with numbering
    currentData.forEach(item => {
        const row = document.createElement('tr');
        const cellCheckbox = document.createElement('td');
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'row-checkbox';
        checkbox.value = item.uuid;
        checkbox.checked = selectedIds.has(item.uuid) || isSelectAllChecked;
        checkbox.addEventListener('change', () => {
            if (checkbox.checked) {
                selectedIds.add(item.uuid);
            } else {
                selectedIds.delete(item.uuid);
                isSelectAllChecked = false; // Uncheck select_all if any checkbox is unchecked
                document.getElementById('select_all').checked = false;
            }
        });
        cellCheckbox.appendChild(checkbox);
        row.appendChild(cellCheckbox);

        selectedFields.forEach(field => {
            const cell = document.createElement('td');
            const cellValue = item[field] || 'N/A'; // Use field directly from item
            
            if (typeof cellValue === 'string' && cellValue.length > 80) {
                const shortValue = cellValue.substring(0, 80) + '...';
                cell.innerHTML = `<span class="viewable-text">${shortValue}</span>`;
                cell.addEventListener('click', () => {
                    document.getElementById('modalText').textContent = cellValue;
                    document.getElementById('myModal').style.display = "block";
                });
            } else {
                cell.textContent = cellValue;
            }

            row.appendChild(cell);
        });

        tableBody.appendChild(row);
    });

    // Add event listener to the select all checkbox
    const selectAllCheckbox = document.getElementById('select_all');
    selectAllCheckbox.checked = isSelectAllChecked; // Preserve the select_all state
    selectAllCheckbox.addEventListener('change', toggleSelectAllCheckboxes);

    // Add event listener to the "Add back to plot" link
    document.getElementById('add_back_plot').addEventListener('click', addBackToPlot);
    document.getElementById('removeFromRAGSearch').addEventListener('click', removeFromRAGSearch);
    
}

// Function to select or deselect all row checkboxes
function toggleSelectAllCheckboxes(event) {
    isSelectAllChecked = event.target.checked;
    const checkboxes = document.querySelectorAll('.row-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.checked = isSelectAllChecked;
        if (checkbox.checked) {
            selectedIds.add(checkbox.value);
        } else {
            selectedIds.delete(checkbox.value);
        }
    });
}

// Function to create a resize handle for table columns
function createResizeHandle() {
    const resizeHandle = document.createElement('div');
    resizeHandle.className = 'resize-handle';

    resizeHandle.addEventListener('mousedown', initResize, false);

    return resizeHandle;
}

// Function to initialize column resizing
function initResize(e) {
    const th = e.target.parentElement;
    const startX = e.pageX;
    const startWidth = parseInt(document.defaultView.getComputedStyle(th).width, 10);

    function doDrag(e) {
        th.style.width = startWidth + e.pageX - startX + 'px';
    }

    function stopDrag() {
        document.documentElement.removeEventListener('mousemove', doDrag, false);
        document.documentElement.removeEventListener('mouseup', stopDrag, false);
    }

    document.documentElement.addEventListener('mousemove', doDrag, false);
    document.documentElement.addEventListener('mouseup', stopDrag, false);
}

// Function to select or deselect all row checkboxes
function toggleSelectAllCheckboxes(event) {
    const checkboxes = document.querySelectorAll('.row-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.checked = event.target.checked;
        if (checkbox.checked) {
            selectedIds.add(checkbox.value);
        } else {
            selectedIds.delete(checkbox.value);
        }
    });
}


// Function to send selected data's 'uuid' to the server
function removeFromRAGSearch(event) {
    event.preventDefault();

    const selectedCheckboxes = document.querySelectorAll('.row-checkbox:checked');
    const selectedIdsArray = Array.from(selectedIds);

    fetch(`/plotV1/remove_from_rag`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ selected_ids: selectedIdsArray })
    })
    .then(response => response.json())
    .then(data => {
        console.log('Selected embeddings sent successfully:', data);
        alert('Selected embeddings sent successfully');
    })
    .catch(error => {
        console.error('Error sending selected embeddings:', error);
        alert('Failed to send selected embeddings');
    });
}

// Function to send selected data's 'uuid' to the server
function addBackToPlot(event) {
    event.preventDefault();

    const selectedCheckboxes = document.querySelectorAll('.row-checkbox:checked');
    const selectedIdsArray = Array.from(selectedIds);

    fetch(`/plotV1/add_back_points`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ selected_ids: selectedIdsArray })
    })
    .then(response => response.json())
    .then(data => {
        console.log('Selected embeddings sent successfully:', data);
        alert('Selected embeddings sent successfully');
    })
    .catch(error => {
        console.error('Error sending selected embeddings:', error);
        alert('Failed to send selected embeddings');
    });
}

// Get the modals
const modal = document.getElementById("myModal");
const configModal = document.getElementById("configModal");

// Get the <span> element that closes the modals
const span = document.getElementsByClassName("close")[0];
const spanConfig = document.getElementsByClassName("close-config")[0];

// When the user clicks on <span> (x), close the modals
span.onclick = function() {
    modal.style.display = "none";
}

spanConfig.onclick = function() {
    configModal.style.display = "none";
}

// When the user clicks anywhere outside of the modals, close them
window.onclick = function(event) {
    if (event.target == modal) {
        modal.style.display = "none";
    }
    if (event.target == configModal) {
        configModal.style.display = "none";
    }
}

// Function to load field names into config table
async function loadFieldNames() {
    try {
        const response = await fetch('/data/retrieve/field_names');
        if (!response.ok) {
            throw new Error(`Error fetching field names: ${response.statusText}`);
        }
        const fieldNames = await response.json();
        const tableBody = document.getElementById('config_table').getElementsByTagName('tbody')[0];

        // Clear any existing rows
        tableBody.innerHTML = '';

        // Add new rows with checkboxes
        fieldNames.forEach(field => {
            const row = document.createElement('tr');
            const cellField = document.createElement('td');
            const cellSelect = document.createElement('td');
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.checked = selectedFields.includes(field);

            cellField.textContent = field;
            cellSelect.appendChild(checkbox);

            row.appendChild(cellField);
            row.appendChild(cellSelect);
            tableBody.appendChild(row);
        });
    } catch (error) {
        console.error('Error loading field names:', error);
    }
}

// Function to select or deselect all checkboxes
function toggleSelectAll(selectAll) {
    const checkboxes = document.querySelectorAll('#config_table tbody input[type="checkbox"]');
    checkboxes.forEach(checkbox => {
        checkbox.checked = selectAll;
    });
}

// Function to apply config and reload embeddings
function applyConfig() {
    const checkboxes = document.querySelectorAll('#config_table tbody input[type="checkbox"]');
    const newSelectedFields = [];

    checkboxes.forEach(checkbox => {
        if (checkbox.checked) {
            newSelectedFields.push(checkbox.closest('tr').children[0].textContent);
        }
    });

    selectedFields = newSelectedFields; // Update selectedFields directly
    loadSelectedEmbeddings(selectedFields); // Reload table with new selected fields
    configModal.style.display = "none"; // Close the config modal
}


// Function to sort the table based on a column
function sortTable(column) {
    const table = document.getElementById('embeddings_table');
    const rows = Array.from(table.rows).slice(1); // Exclude the header row
    const columnIndex = Array.from(table.rows[0].cells).findIndex(cell => cell.textContent.includes(column));

    rows.sort((a, b) => {
        const aText = a.cells[columnIndex].textContent.trim();
        const bText = b.cells[columnIndex].textContent.trim();

        if (ascending) {
            return aText.localeCompare(bText, undefined, {numeric: true});
        } else {
            return bText.localeCompare(aText, undefined, {numeric: true});
        }
    });

    ascending = !ascending; // Toggle sort order

    // Reattach sorted rows
    rows.forEach(row => table.appendChild(row));

    // Update sort button appearance
    document.querySelectorAll('.sort-btn').forEach(btn => btn.classList.remove('desc'));
    if (!ascending) {
        document.querySelectorAll(`.sort-btn[onclick="sortTable('${column}')"]`).forEach(btn => btn.classList.add('desc'));
    }
}

// Event listener for config table button
document.getElementById('config_table_btn').addEventListener('click', () => {
    configModal.style.display = "block";
    loadFieldNames();
});

// Event listener for apply config button
document.getElementById('apply_config_btn').addEventListener('click', applyConfig);

// Event listener for cancel config button
document.getElementById('cancel_config_btn').addEventListener('click', () => {
    configModal.style.display = "none";
});

// Event listener for select all button
document.getElementById('select_all_btn').addEventListener('click', () => toggleSelectAll(true));

// Event listener for deselect all button
document.getElementById('deselect_all_btn').addEventListener('click', () => toggleSelectAll(false));

// Load selected embeddings every 5 seconds
setInterval(() => loadSelectedEmbeddings(selectedFields), 1000);
window.onload = () => loadSelectedEmbeddings(selectedFields);

```

```javascript
// plotly_project\static\script3.js

// script2.js
let selectedFields = ['uuid', 'filename', 'page_content']; // Default selected fields
let ascending = true; // Sort order
let currentData = []; // Store the current data for updating fields
let selectedIds = new Set(); // Store selected IDs
let isSelectAllChecked = false; // Track the state of the select_all checkbox

async function loadSelectedEmbeddings(fieldNames = selectedFields) {
    try {
        const queryString = fieldNames.map(field => `fields=${encodeURIComponent(field)}`).join('&');
        const response = await fetch(`/plotV1/scatter_plot/nonvisible?${queryString}`);
        if (!response.ok) {
            throw new Error(`Error fetching data: ${response.statusText}`);
        }
        const data = await response.json();
        const lastUpdateTime = data.LAST_UPDATE_TIME; // Extract the timestamp
        currentData = data.rows; // Assuming `rows` is the array of row data

        // Update SQLite database with the retrieved data
        await updateSQLiteDatabase(currentData, lastUpdateTime);

        // Now update the table
        updateTable();
    } catch (error) {
        console.error('Error loading selected embeddings:', error);
    }
}

async function updateSQLiteDatabase(data, lastUpdateTime) {
    // Initialize SQLite_Manager
    const SM = new SQLite_Manager('embeddings_db'); // Or the appropriate name

    // Add data to SQLite
    for (const row of data) {
        await SM.set_field_values_by_ids([row.uuid], 'plot_code', row.plot_code);
        await SM.set_field_values_by_ids([row.uuid], 'filename', row.filename);
        await SM.set_field_values_by_ids([row.uuid], 'page_content', row.page_content);
        // Add more fields as necessary
    }

    // Store the last update time in SQLite (or in local storage for easy access)
    localStorage.setItem('LAST_UPDATE_TIME', lastUpdateTime);
}


async function updateTable() {
    const SM = new SQLite_Manager('embeddings_db'); // Initialize SQLite_Manager

    const tableBody = document.getElementById('embeddings_table').getElementsByTagName('tbody')[0];
    tableBody.innerHTML = ''; // Clear any existing rows

    const tableHeaders = document.getElementById('table_headers');
    tableHeaders.innerHTML = '<th><input type="checkbox" id="select_all"></th>'; // Clear existing headers

    // Add new table headers based on selected fields
    selectedFields.forEach(field => {
        const th = document.createElement('th');
        th.innerHTML = `${field} <button class="sort-btn" onclick="sortTable('${field}')"></button>`;
        th.appendChild(createResizeHandle());
        tableHeaders.appendChild(th);
    });

    // Query SQLite for data
    const query = 'SELECT * FROM embeddings_table WHERE plot_code = 1'; // Adjust as necessary
    const data = await SM.get_filtered_data(query);

    data.forEach(item => {
        const row = document.createElement('tr');
        const cellCheckbox = document.createElement('td');
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'row-checkbox';
        checkbox.value = item.uuid;
        checkbox.checked = selectedIds.has(item.uuid) || isSelectAllChecked;
        checkbox.addEventListener('change', () => {
            if (checkbox.checked) {
                selectedIds.add(item.uuid);
            } else {
                selectedIds.delete(item.uuid);
                isSelectAllChecked = false; // Uncheck select_all if any checkbox is unchecked
                document.getElementById('select_all').checked = false;
            }
        });
        cellCheckbox.appendChild(checkbox);
        row.appendChild(cellCheckbox);

        selectedFields.forEach(field => {
            const cell = document.createElement('td');
            const cellValue = item[field] || 'N/A';
            
            if (typeof cellValue === 'string' && cellValue.length > 80) {
                const shortValue = cellValue.substring(0, 80) + '...';
                cell.innerHTML = `<span class="viewable-text">${shortValue}</span>`;
                cell.addEventListener('click', () => {
                    document.getElementById('modalText').textContent = cellValue;
                    document.getElementById('myModal').style.display = "block";
                });
            } else {
                cell.textContent = cellValue;
            }

            row.appendChild(cell);
        });

        tableBody.appendChild(row);
    });

    // Handle "select all" checkbox and other UI updates
    document.getElementById('select_all').addEventListener('change', toggleSelectAllCheckboxes);
}

async function manageSQLiteMemory(SM, maxMemorySize) {
    // Query to determine the current size of the SQLite database
    const sizeQuery = "SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size();";
    const sizeResult = await SM.execute_query(sizeQuery);
    const currentSize = sizeResult.size;

    if (currentSize > maxMemorySize) {
        // Implement logic to delete old or least recently used data
        await SM.purge_oldest_data();
    }
}

async function synchronizeWithServer() {
    const lastUpdateTime = localStorage.getItem('LAST_UPDATE_TIME');
    const response = await fetch(`/data/sync?last_update_time=${lastUpdateTime}`);
    if (!response.ok) {
        throw new Error(`Error syncing with server: ${response.statusText}`);
    }
    const data = await response.json();
    await updateSQLiteDatabase(data.rows, data.LAST_UPDATE_TIME);
}


// Function to select or deselect all row checkboxes
function toggleSelectAllCheckboxes(event) {
    isSelectAllChecked = event.target.checked;
    const checkboxes = document.querySelectorAll('.row-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.checked = isSelectAllChecked;
        if (checkbox.checked) {
            selectedIds.add(checkbox.value);
        } else {
            selectedIds.delete(checkbox.value);
        }
    });
}

// Function to create a resize handle for table columns
function createResizeHandle() {
    const resizeHandle = document.createElement('div');
    resizeHandle.className = 'resize-handle';

    resizeHandle.addEventListener('mousedown', initResize, false);

    return resizeHandle;
}

// Function to initialize column resizing
function initResize(e) {
    const th = e.target.parentElement;
    const startX = e.pageX;
    const startWidth = parseInt(document.defaultView.getComputedStyle(th).width, 10);

    function doDrag(e) {
        th.style.width = startWidth + e.pageX - startX + 'px';
    }

    function stopDrag() {
        document.documentElement.removeEventListener('mousemove', doDrag, false);
        document.documentElement.removeEventListener('mouseup', stopDrag, false);
    }

    document.documentElement.addEventListener('mousemove', doDrag, false);
    document.documentElement.addEventListener('mouseup', stopDrag, false);
}

// Function to select or deselect all row checkboxes
function toggleSelectAllCheckboxes(event) {
    const checkboxes = document.querySelectorAll('.row-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.checked = event.target.checked;
        if (checkbox.checked) {
            selectedIds.add(checkbox.value);
        } else {
            selectedIds.delete(checkbox.value);
        }
    });
}


// Function to send selected data's 'uuid' to the server
function removeFromRAGSearch(event) {
    event.preventDefault();

    const selectedCheckboxes = document.querySelectorAll('.row-checkbox:checked');
    const selectedIdsArray = Array.from(selectedIds);

    fetch(`/plotV1/remove_from_rag`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ selected_ids: selectedIdsArray })
    })
    .then(response => response.json())
    .then(data => {
        console.log('Selected embeddings sent successfully:', data);
        alert('Selected embeddings sent successfully');
    })
    .catch(error => {
        console.error('Error sending selected embeddings:', error);
        alert('Failed to send selected embeddings');
    });
}

// Function to send selected data's 'uuid' to the server
function addBackToPlot(event) {
    event.preventDefault();

    const selectedCheckboxes = document.querySelectorAll('.row-checkbox:checked');
    const selectedIdsArray = Array.from(selectedIds);

    fetch(`/plotV1/add_back_points`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ selected_ids: selectedIdsArray })
    })
    .then(response => response.json())
    .then(data => {
        console.log('Selected embeddings sent successfully:', data);
        alert('Selected embeddings sent successfully');
    })
    .catch(error => {
        console.error('Error sending selected embeddings:', error);
        alert('Failed to send selected embeddings');
    });
}

// Get the modals
const modal = document.getElementById("myModal");
const configModal = document.getElementById("configModal");

// Get the <span> element that closes the modals
const span = document.getElementsByClassName("close")[0];
const spanConfig = document.getElementsByClassName("close-config")[0];

// When the user clicks on <span> (x), close the modals
span.onclick = function() {
    modal.style.display = "none";
}

spanConfig.onclick = function() {
    configModal.style.display = "none";
}

// When the user clicks anywhere outside of the modals, close them
window.onclick = function(event) {
    if (event.target == modal) {
        modal.style.display = "none";
    }
    if (event.target == configModal) {
        configModal.style.display = "none";
    }
}

// Function to load field names into config table
async function loadFieldNames() {
    try {
        const response = await fetch('/data/retrieve/field_names');
        if (!response.ok) {
            throw new Error(`Error fetching field names: ${response.statusText}`);
        }
        const fieldNames = await response.json();
        const tableBody = document.getElementById('config_table').getElementsByTagName('tbody')[0];

        // Clear any existing rows
        tableBody.innerHTML = '';

        // Add new rows with checkboxes
        fieldNames.forEach(field => {
            const row = document.createElement('tr');
            const cellField = document.createElement('td');
            const cellSelect = document.createElement('td');
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.checked = selectedFields.includes(field);

            cellField.textContent = field;
            cellSelect.appendChild(checkbox);

            row.appendChild(cellField);
            row.appendChild(cellSelect);
            tableBody.appendChild(row);
        });
    } catch (error) {
        console.error('Error loading field names:', error);
    }
}

// Function to select or deselect all checkboxes
function toggleSelectAll(selectAll) {
    const checkboxes = document.querySelectorAll('#config_table tbody input[type="checkbox"]');
    checkboxes.forEach(checkbox => {
        checkbox.checked = selectAll;
    });
}

// Function to apply config and reload embeddings
function applyConfig() {
    const checkboxes = document.querySelectorAll('#config_table tbody input[type="checkbox"]');
    const newSelectedFields = [];

    checkboxes.forEach(checkbox => {
        if (checkbox.checked) {
            newSelectedFields.push(checkbox.closest('tr').children[0].textContent);
        }
    });

    selectedFields = newSelectedFields; // Update selectedFields directly
    loadSelectedEmbeddings(selectedFields); // Reload table with new selected fields
    configModal.style.display = "none"; // Close the config modal
}


// Function to sort the table based on a column
function sortTable(column) {
    const table = document.getElementById('embeddings_table');
    const rows = Array.from(table.rows).slice(1); // Exclude the header row
    const columnIndex = Array.from(table.rows[0].cells).findIndex(cell => cell.textContent.includes(column));

    rows.sort((a, b) => {
        const aText = a.cells[columnIndex].textContent.trim();
        const bText = b.cells[columnIndex].textContent.trim();

        if (ascending) {
            return aText.localeCompare(bText, undefined, {numeric: true});
        } else {
            return bText.localeCompare(aText, undefined, {numeric: true});
        }
    });

    ascending = !ascending; // Toggle sort order

    // Reattach sorted rows
    rows.forEach(row => table.appendChild(row));

    // Update sort button appearance
    document.querySelectorAll('.sort-btn').forEach(btn => btn.classList.remove('desc'));
    if (!ascending) {
        document.querySelectorAll(`.sort-btn[onclick="sortTable('${column}')"]`).forEach(btn => btn.classList.add('desc'));
    }
}

// Event listener for config table button
document.getElementById('config_table_btn').addEventListener('click', () => {
    configModal.style.display = "block";
    loadFieldNames();
});

// Event listener for apply config button
document.getElementById('apply_config_btn').addEventListener('click', applyConfig);

// Event listener for cancel config button
document.getElementById('cancel_config_btn').addEventListener('click', () => {
    configModal.style.display = "none";
});

// Event listener for select all button
document.getElementById('select_all_btn').addEventListener('click', () => toggleSelectAll(true));

// Event listener for deselect all button
document.getElementById('deselect_all_btn').addEventListener('click', () => toggleSelectAll(false));

// Load selected embeddings every 5 seconds
setInterval(() => loadSelectedEmbeddings(selectedFields), 1000);
window.onload = () => loadSelectedEmbeddings(selectedFields);

```

```css
/* plotly_project\static\style.css */

/* style.css */
body {
    display: flex;  /* Sets the body to use flexbox layout */
    justify-content: center;  /* Aligns content to the center horizontally */
    align-items: center;  /* Centers content vertically */
    flex-direction: column;  /* Stacks content in a column */
    min-height: 100vh;  /* Ensures the body takes up at least the full viewport height */
    margin: 0;  /* Removes default margin */
    padding: 2vh;  /* Adds padding to the body using viewport height */
    background-color: #f4f4f4;  /* Optional: Background color for better visualization */
}

/* Hidden by default, shown when necessary */
.hidden {
    display: none;
}

/* Style for error message displayed during initialization check */
.error-message {
    color: red;
    font-size: 3vh;
    text-align: center;
}

/* Style for the Initialize Database button */
#init-database-btn {
    padding: 2vh 4vw;
    font-size: 2vh;
    margin-top: 2vh;
}

/* Ensure the main content is hidden until the database is initialized */
#main-content {
    display: none;

    .control-container {
        display: flex;
        align-items: center;
        margin-bottom: 2vh;  /* Margin using viewport height */
        gap: 2vw;  /* Gap using viewport width */
    }
    
    .dropdown-container {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
    }
    
    #plot-select, #operation-select {
        padding: 1vh 2vw;  /* Padding using viewport units */
        font-size: 1.6vh;  /* Font size using viewport height */
    }
    
    .plot-container {
        width: 80vw;  /* Makes the container take 80% of the viewport width */
        height: 60vh; /* Makes the container take 60% of the viewport height */
        padding: 2vh;  /* Padding using viewport height */
        background-color: white;  /* Optional: Background color for the plot container */
        box-shadow: 0 0 1vh rgba(0, 0, 0, 0.1);  /* Optional: Box shadow for better appearance */
        margin-bottom: 2vh;  /* Margin using viewport height */
        text-align: center;  /* Center-aligns the text inside the container */
        display: flex;  /* Sets the container to use flexbox layout */
        justify-content: center;  /* Centers plot content horizontally */
        align-items: center;  /* Centers plot content vertically */
        z-index: 1; /* Lower z-index for plot container */
    }
    
    .plots-wrapper {
        display: flex;  /* Sets the wrapper to use flexbox layout */
        flex-direction: column;  /* Stacks content in a column */
        align-items: center;  /* Centers content horizontally */
        justify-content: flex-start;  /* Aligns content to the start vertically */
        width: 100%;  /* Makes the wrapper take the full width of its parent */
    }
    
    .button-container {
        margin-top: 2vh;
        margin-bottom: 2vh; /* Adds space below the buttons */
        display: flex;
        justify-content: center;
        gap: 2vw;  /* Gap using viewport width */
        z-index: 2;  /* Ensure the buttons are on top */
        position: relative; /* Ensure the buttons are positioned correctly */
    }
    
    button {
        padding: 1vh 2vw;  /* Padding using viewport units */
        font-size: 1.6vh;  /* Font size using viewport height */
    }
    
}

```

```css
/* plotly_project\static\style2.css */

/* style2.css */
body {
    font-family: Arial, sans-serif;
    background-color: #f4f4f4;
    margin: 0;
    padding: 20px;
    overflow-x: auto; /* Add this line to enable horizontal scrolling */
}
table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 20px;
    table-layout: auto; /* Change to auto to handle resizing */
}
table, th, td {
    border: 1px solid #ddd;
}
th, td {
    padding: 8px;
    text-align: left;
    max-width: 150px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    position: relative; /* Add this line */
}
th:first-child, td:first-child {
    width: 40px; /* Set a fixed width for the first column */
}
th {
    background-color: #f2f2f2;
    position: relative;
}
th a {
    color: blue;
    text-decoration: none;
    cursor: pointer;
}
th a:hover {
    text-decoration: underline;
}
.modal {
    display: none;
    position: fixed;
    z-index: 1;
    left: 0;
    top: 0;
    width: 100%;
    height: 100%;
    overflow: auto;
    background-color: rgb(0,0,0);
    background-color: rgba(0,0,0,0.4);
}
.modal-content {
    background-color: #fefefe;
    margin: 15% auto;
    padding: 20px;
    border: 1px solid #888;
    width: 80%;
    max-height: 70%;
    overflow-y: auto;
}
.close, .close-config {
    color: #aaa;
    float: right;
    font-size: 28px;
    font-weight: bold;
}
.close:hover, .close:focus, .close-config:hover, .close-config:focus {
    color: black;
    text-decoration: none;
    cursor: pointer;
}
button.sort-btn {
    background: none;
    border: none;
    cursor: pointer;
    color: #007BFF;
    font-size: 12px;
    margin-left: 5px;
}
button.sort-btn::after {
    content: '\25B2'; /* Up arrow */
    display: inline-block;
    margin-left: 2px;
    font-size: 12px;
}
button.sort-btn.desc::after {
    content: '\25BC'; /* Down arrow */
}
button {
    padding: 10px 20px;
    margin-bottom: 20px;
    font-size: 16px;
    cursor: pointer;
}
.viewable-text {
    /*color: blue;*/
    cursor: pointer;
}
.viewable-text:hover {
    text-decoration: underline;
}
.resize-handle {
    position: absolute;
    top: 0;
    right: 0;
    width: 5px;
    height: 100%;
    cursor: col-resize;
    background-color: transparent;
}

```

```css
/* plotly_project\static\style3.css */

/* style2.css */
body {
    font-family: Arial, sans-serif;
    background-color: #f4f4f4;
    margin: 0;
    padding: 20px;
    overflow-x: auto; /* Add this line to enable horizontal scrolling */
}
table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 20px;
    table-layout: auto; /* Change to auto to handle resizing */
}
table, th, td {
    border: 1px solid #ddd;
}
th, td {
    padding: 8px;
    text-align: left;
    max-width: 150px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    position: relative; /* Add this line */
}
th:first-child, td:first-child {
    width: 40px; /* Set a fixed width for the first column */
}
th {
    background-color: #f2f2f2;
    position: relative;
}
th a {
    color: blue;
    text-decoration: none;
    cursor: pointer;
}
th a:hover {
    text-decoration: underline;
}
.modal {
    display: none;
    position: fixed;
    z-index: 1;
    left: 0;
    top: 0;
    width: 100%;
    height: 100%;
    overflow: auto;
    background-color: rgb(0,0,0);
    background-color: rgba(0,0,0,0.4);
}
.modal-content {
    background-color: #fefefe;
    margin: 15% auto;
    padding: 20px;
    border: 1px solid #888;
    width: 80%;
    max-height: 70%;
    overflow-y: auto;
}
.close, .close-config {
    color: #aaa;
    float: right;
    font-size: 28px;
    font-weight: bold;
}
.close:hover, .close:focus, .close-config:hover, .close-config:focus {
    color: black;
    text-decoration: none;
    cursor: pointer;
}
button.sort-btn {
    background: none;
    border: none;
    cursor: pointer;
    color: #007BFF;
    font-size: 12px;
    margin-left: 5px;
}
button.sort-btn::after {
    content: '\25B2'; /* Up arrow */
    display: inline-block;
    margin-left: 2px;
    font-size: 12px;
}
button.sort-btn.desc::after {
    content: '\25BC'; /* Down arrow */
}
button {
    padding: 10px 20px;
    margin-bottom: 20px;
    font-size: 16px;
    cursor: pointer;
}
.viewable-text {
    /*color: blue;*/
    cursor: pointer;
}
.viewable-text:hover {
    text-decoration: underline;
}
.resize-handle {
    position: absolute;
    top: 0;
    right: 0;
    width: 5px;
    height: 100%;
    cursor: col-resize;
    background-color: transparent;
}

```

```css
/* plotly_project\static\weaviateui\weaviateui.css */

body {
    font-family: Arial, sans-serif;
    margin: 0;
    padding: 0;
    background-color: #f4f4f4;
}

.container {
    width: 80%;
    margin: 0 auto;
    padding: 20px;
    background-color: #fff;
    border-radius: 8px;
    box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
}

h1 {
    text-align: center;
    color: #333;
}

.input-group {
    margin: 10px 0;
}

.input-group label {
    display: block;
    margin-bottom: 5px;
    font-weight: bold;
}

.input-group input {
    width: 100%;
    padding: 8px;
    box-sizing: border-box;
    border: 1px solid #ccc;
    border-radius: 4px;
}

.button-group {
    margin: 20px 0;
    text-align: center;
}

.button-group button {
    margin: 5px;
    padding: 10px 20px;
    border: none;
    border-radius: 4px;
    background-color: #007bff;
    color: white;
    cursor: pointer;
}

#clearButton {
    display: block;
    width: 100%;
    padding: 10px;
    border: none;
    border-radius: 4px;
    background-color: #dc3545;
    color: white;
    cursor: pointer;
    margin-bottom: 20px;
}

.message-window {
    padding: 10px;
    border: 1px solid #ccc;
    border-radius: 4px;
    background-color: #f9f9f9;
    min-height: 100px;
    white-space: pre-wrap;
}

```

```html
<!-- plotly_project\static\weaviateui\weaviateui.html -->

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RMOperations Interface</title>
    <link rel="stylesheet" href="/static/weaviateui/weaviateui.css">
</head>
<body>
    <div class="container">
        <h1>RMOperations Interface</h1>

        <!-- Input boxes for settings -->
        <div class="input-group">
            <label for="setting1">Setting 1:</label>
            <input type="text" id="setting1">
        </div>
        <div class="input-group">
            <label for="setting2">Setting 2:</label>
            <input type="text" id="setting2">
        </div>
        <div class="input-group">
            <label for="setting3">Setting 3:</label>
            <input type="text" id="setting3">
        </div>
        <div class="input-group">
            <label for="setting4">Setting 4:</label>
            <input type="text" id="setting4">
        </div>
        <div class="input-group">
            <label for="setting5">Setting 5:</label>
            <input type="text" id="setting5">
        </div>

        <!-- Buttons for RMOperations methods -->
        <div class="button-group">
            <button onclick="retrievePDF('test.pdf')">View PDF</button>
            <button onclick="sendRequest('set_all_values_per_filename')">Set All Values for a Filename </button>
            <button onclick="sendRequest('get_collection_schema')">Get Schema Collection</button>
            <button onclick="sendRequest('add_all_to_rag')">Add All Data Back To RAG Search</button>
            <button onclick="sendRequest('set_ids_to_nonvisible')">Set IDs to Nonvisible</button>
            <button onclick="sendRequest('get_filtered_data')">Get Filtered Data</button>
            <button onclick="sendRequest('force_initialize_fields')">Force Initialize Fields</button>
            <button onclick="sendRequest('get_all_collection_names')">Get Available Collections</button>
        </div>

        <!-- Clear button -->
        <button id="clearButton" onclick="clearInputs()">Clear</button>

        <!-- Message window for displaying responses -->
        <div class="message-window" id="messageWindow"></div>
    </div>

    <script src="/static/weaviateui/weaviateui.js"></script>
</body>
</html>

```

```javascript
// plotly_project\static\weaviateui\weaviateui.js

// Function to send request to the backend
function sendRequest(endpoint) {
    const settings = {};

    // Collecting input values
    for (let i = 1; i <= 5; i++) {
        const value = document.getElementById(`setting${i}`).value;
        if (value) {
            settings[`setting${i}`] = value;
        }
    }

    // Creating the request object
    const requestOptions = {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
    };

    // Sending the request
    fetch(`http://localhost:8025/data/${endpoint}`, requestOptions)
        .then(response => response.json())
        .then(data => displayMessage(data))
        .catch(error => displayMessage(`Error: ${error}`));
}

// Function to display response in the message window
function displayMessage(message) {
    const messageWindow = document.getElementById('messageWindow');
    messageWindow.innerText = JSON.stringify(message, null, 2);
}

// Function to retrieve and display a PDF
function retrievePDF(pdfName) {
    const url = `http://localhost:8025/documents/pdf/${pdfName}`;
    
    // Open the PDF in a new browser window
    window.open(url, '_blank');
}

// Function to clear input fields
function clearInputs() {
    for (let i = 1; i <= 5; i++) {
        document.getElementById(`setting${i}`).value = '';
    }
    document.getElementById('messageWindow').innerText = '';
}

```
