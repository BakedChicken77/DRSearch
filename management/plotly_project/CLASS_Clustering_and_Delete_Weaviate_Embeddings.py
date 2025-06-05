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
