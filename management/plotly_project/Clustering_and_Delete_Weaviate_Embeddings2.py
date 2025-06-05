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

    
