
# run_ingest.py

from pathlib import Path
import os
import sys
import argparse
from datetime import datetime
from typing import List

# Your existing imports and code here...
from partition_pdf_and_docx_Final5 import process_documents
# from Get_SEP_Files import get_files
from Get_Docs_From_EmPower_with_Auth2 import download_documents
from sep_file_manager import SEPs
from document_filter import filter_documents_by_type

# Set up argument parser
parser = argparse.ArgumentParser(description="Process documents with optional parameters.")

parser.add_argument("index", nargs='?', default="JAC_SKE_PROD_TEST", help="Index name (namespace) to use.")

parser.add_argument("--max_chunk_size", type=int, default=5000, help="Maximum chunk size.")
parser.add_argument("--html_summaries", type=lambda x: (str(x).lower() == 'true'), default=True, help="Generate HTML summaries (True/False).")
parser.add_argument("--store_debug_files_files", type=lambda x: (str(x).lower() == 'true'), default=True, help="Store debug files (True/False).")
parser.add_argument("--element_dir_path", type=str, default="elements_dir", help="Path to elements directory.")
parser.add_argument("--docs_to_ingest", type=str, default="docs", help="Path to documents to ingest.")

args = parser.parse_args()

# Assign variables from arguments
namespace = args.index
max_chunk_size = args.max_chunk_size
html_summaries = args.html_summaries
store_debug_files_files = args.store_debug_files_files
element_dir_path = Path(args.element_dir_path)
docs_to_ingest = Path(args.docs_to_ingest)
json_dir_path = element_dir_path  # Assuming json_dir_path is the same as element_dir_path

# Debug print statements (optional)
print(f"Using namespace: {namespace}")
print(f"max_chunk_size: {max_chunk_size}")
print(f"html_summaries: {html_summaries}")
print(f"store_debug_files_files: {store_debug_files_files}")
print(f"element_dir_path: {element_dir_path}")
print(f"docs_to_ingest: {docs_to_ingest}")

process_documents(
    WEAVIATE_DOCS_INDEX_NAME=namespace,
    max_chunk_size=max_chunk_size,
    doc_directory=docs_to_ingest,
    elements_directory=element_dir_path,
    json_dir=json_dir_path,
    html_summaries=html_summaries
)
