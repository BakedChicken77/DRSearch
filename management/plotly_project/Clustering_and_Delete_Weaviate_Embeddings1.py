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
