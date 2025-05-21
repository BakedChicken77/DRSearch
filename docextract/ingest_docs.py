
from pathlib import Path
import os
from datetime import datetime
from typing import List
from partition_pdf_and_docx_Final5 import process_documents
from Get_Docs_From_EmPower_with_DocViewer import download_documents
from sep_file_manager import SEPs
from document_filter import filter_documents_by_type


def Ingest(collection):
    namespace = collection #"SEPs_F_T_C_W_A_V_Summaries"
    max_chunk_size = 10000
    html_summaries = True
    store_debug_files_files = True

    # EmPower Document Search Parameters
    Desired_PartNumber = '%22012%'
    Undesired_PartNumber = 'SK%'
    Document_Types = ['docx']#, 'pdf']
    After_This_Data_YYYY_MM_DD = '2020-01-01'

    # Construct the directories using the namespace and current date
    Base_Dir = Path(r"G:\Unstructured_Processing\Ingested")
    current_date = datetime.now().strftime("_%Y%m%d")
    Doc_dir = Base_Dir / namespace
    element_dir = Doc_dir / "elements"
    json_dir = Doc_dir / "jsons"

    Doc_dir.mkdir(parents=True, exist_ok=True)

    element_dir_path = None
    json_dir_path = None

    counter = 0
    if store_debug_files_files:
        while True:
            element_dir_path = element_dir / f"{current_date}_{counter}"
            json_dir_path = json_dir / f"{current_date}_{counter}"
            
            if not element_dir_path.exists() and not json_dir_path.exists():
                break
            counter += 1

        element_dir_path.mkdir(parents=True, exist_ok=True)
        json_dir_path.mkdir(parents=True, exist_ok=True)

    print(f"Storing ingestion debug files in: {element_dir_path}, {json_dir_path}")

    file_loading_process = namespace.lower()

    if "sep" in file_loading_process:
        seps = SEPs()
        docs_to_ingest = seps.get_files()
        doc_types = ['F', 'T', 'C', 'W', 'A', 'V']
        docs_to_ingest, removed_paths = filter_documents_by_type(docs_to_ingest, doc_types)

    elif "jac" in file_loading_process:
        docs_to_ingest = Doc_dir / "JACSKE_Docs"
        docs_to_ingest.mkdir(parents=True, exist_ok=True)

        download_documents(
            download_folder=docs_to_ingest, 
            Desired_PartNumber=Desired_PartNumber, 
            Document_Types=Document_Types, 
            Undesired_PartNumber=Undesired_PartNumber,
            After_This_Data_YYYY_MM_DD=After_This_Data_YYYY_MM_DD
        )

    process_documents(
        WEAVIATE_DOCS_INDEX_NAME=namespace, 
        max_chunk_size=max_chunk_size, 
        doc_directory=docs_to_ingest, 
        elements_directory=element_dir_path, 
        json_dir=json_dir_path,
        html_summaries=html_summaries
    )

    return

if __name__ == "__main__":
    Ingest("SEP_test_20241002")
