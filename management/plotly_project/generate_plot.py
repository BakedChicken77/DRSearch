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
