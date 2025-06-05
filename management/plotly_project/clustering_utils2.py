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
