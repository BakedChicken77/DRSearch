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
