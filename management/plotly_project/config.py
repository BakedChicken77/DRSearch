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
