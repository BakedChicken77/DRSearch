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
