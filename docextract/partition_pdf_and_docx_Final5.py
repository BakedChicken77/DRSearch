## docker cp "C:\Users\Steve.Long\OneDrive - Leonardo DRS\Documents\_AI_TEAM\Ingestion_Docker\partition_pdf_and_docx_Final5.py" unstructured:/app/partition_pdf_and_docx_Final5.py

import os
import json

# Import NLTK and configure the data path to use the pre-copied nltk_data directory.
# This ensures that the necessary NLTK data (such as the 'punkt' tokenizer) is available
# without needing to download it from the web, which is useful for running in a Docker container.
import nltk

nltk.data.path.append("/usr/local/share/nltk_data")

import pypandoc

from unstructured.partition.pdf import partition_pdf
from unstructured.partition.docx import partition_docx
from pathlib import Path
import logging
from typing import Optional, IO

# from typing import Any, Dict
# from unstructured.staging.weaviate import stage_for_weaviate
from unstructured.chunking.title import chunk_by_title
from langchain.indexes import index
from ExtendedSQLRecordManager4 import ExtendedSQLRecordManager
import weaviate
from weaviate.auth import AuthApiKey
from Weaviate_Schema import create_weaviate_schema

# from weaviate.connect import ConnectionParams, ProtocolParams
from langchain_community.vectorstores import Weaviate
from langchain_core.embeddings import Embeddings
from langchain_openai import AzureOpenAIEmbeddings
from openai import AzureOpenAI
from dotenv import load_dotenv
import math

# from bs4 import BeautifulSoup
# from sqlalchemy import inspect
import inspect
from concurrent.futures import ThreadPoolExecutor
import time

# from langchain.prompts import  PromptTemplate
from HTML_Processing import llm_summarize_text_as_html

# from HTML_Processing0 import process_text_as_html
from ingestion_utilities import (
    clean_table_of_contents,
    clean_record_of_changes,
    write_log_to_file,
    process_large_tables,
    process_images,
)
from Acronym_Tools import process_acronym_text_as_html

# from write_all_elements_to_file2 import write_elements_to_text_file2
from unstructured.partition.xlsx import partition_xlsx

# default_html_summary_prompt= """\
# You will be given HTML content produced from partitioning a DOCX file using Unstructured-IO libraries, \
# where the HTML is stored in the metadata as 'text_as_html'. Your task is to provide a detailed, \
# semantically relevant description of the content represented by the HTML. This description will \
# be embedded using OpenAI's 'text-embedding-ada-002' model and used for semantic search purposes.\

# Ensure that your description includes unique terms, column and row names, categories, and table data. \
# However, you do not need to list every column or row. For repetitive labels, generalize them \
# to capture the essence of the content. For example, columns labeled as 'test1', 'test2', \
# 'test3', etc., can be summarized as 'tests'. Similarly, for columns labeled 'transponder \
# test pass/fail', 'ground system test pass/fail', and 'antenna test pass/fail', you can describe \
# them as 'pass/fail results for the transponder, antenna, and ground system'.\

# Your entire response will be embedded, so ensure that your description is only semantically \
# relevant and includes key information that will improve the search capabilities. Write the \
# description directly without prefacing it with phrases like 'The HTML content represents'.\

# If the provided HTML lacks semantic content, respond with 'None'. No semantic content includes \
# HTML that consists of empty tags, tags with only whitespace, purely structural or decorative elements, \
# or any content that does not provide meaningful information for understanding or searching the document.\
# """
# PromptTemplate(
#     input_variables=["max_chunk_size"],
#     template="""
# """


default_html_summary_prompt = """\
Your task is to provide a detailed, semantically relevant description of the provided HTML. \
This HTML represents content extracted from DOCX and PDF files using Unstructured-IO libraries. \
Your description will be converted into a vector embedding for semantic search purposes.

Ensure your description encapsulates unique terms, column/row names, categories, table data, titles, \
labels, and other key information. Minimize common, generic characteristics and focus on details that \
highlight the uniqueness of the content.

Your description shall be no more than 1000 words.

If the HTML lacks semantic content (e.g., empty tags, whitespace, \
purely structural or decorative elements), respond with 'None.' 
If the HTML contains an acronym list, respond with 'I FOUND YOU AN ACRONYM LIST.'

Write descriptions as if viewing the original content, not the HTML. Speak directly to the content \
without prefacing with phrases like 'The HTML content represents.' The reader should not be aware that \
the text was extracted or converted to HTML.
"""

html_content_1shot = """<table>
<thead>
<tr><th>Voltage  </th><th>Max Current  </th><th>Current Limit  </th></tr>
</thead>
<tbody>
<tr><td>22 V ±10%</td><td>5 A          </td><td>7 A            </td></tr>
</tbody>
</table>"""

html_summary_1shot = """\
The table presents electrical specifications for a device, listing voltage, maximum current, \
and current limit. The voltage is specified as 22 volts with a tolerance of plus or minus 10%. \
The maximum current is 5 amperes, and the current limit is 7 amperes.\
"""


# Load environment variables
try:
    load_dotenv()
except Exception as e:
    print(f"Error loading environment variables: {e}")

# Set environment variables
os.environ["CUDA_VISIBLE_DEVICES"] = "0"
os.environ["LOCAL_FILES_ONLY"] = "True"
os.environ["TRANSFORMERS_OFFLINE"] = "True"
os.environ["HF_HUB_OFFLINE"] = "True"
# os.environ['HF_HUB_CACHE'] = "/app/.cache"
# os.environ['UNSTRUCTURED_CACHE_DIR'] = "/app/.cache"

WEAVIATE_URL = os.environ["WEAVIATE_URL"]
WEAVIATE_API_KEY = os.environ["WEAVIATE_API_KEY"]
RECORD_MANAGER_DB_URL = os.getenv("RECORD_MANAGER_DB_URL")

default_api_version = os.getenv("AZURE_OPENAI_API_VERSION")
model_4 = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
default_html_summary_model = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
default_embedder_model = os.getenv("AZURE_OPENAI_EMBEDDER")

# Batch processing and threading configuration
DOCUMENT_BATCH_SIZE = int(os.getenv("DOCUMENT_BATCH_SIZE", "10"))
DOCUMENT_PROCESS_THREADS = int(os.getenv("DOCUMENT_PROCESS_THREADS", "4"))

LLM = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=default_api_version,
)


# Custom formatter to include more granular information
class CustomFormatter(logging.Formatter):
    def format(self, record):
        # Add the class and function name to the log record if available
        frame = inspect.currentframe()
        while frame:
            if "self" in frame.f_locals and frame.f_locals["self"].__class__.__name__ != "CustomFormatter":
                record.class_name = frame.f_locals["self"].__class__.__name__
                break
            frame = frame.f_back
        else:
            record.class_name = "N/A"

        record.function_name = record.funcName
        record.line_number = record.lineno

        # Adjust timestamp precision
        record.asctime = self.formatTime(record, self.datefmt)

        return super().format(record)

    def formatTime(self, record, datefmt=None):
        if datefmt:
            return logging.Formatter.formatTime(self, record, datefmt)
        ct = self.converter(record.created)
        t = time.strftime("%Y-%m-%d %H:%M:%S", ct)
        return t


# Setup logging
log_file_path = Path(__file__).parent / "_RUN_INFO_WARNINGS_AND_ERRORS.txt"
log_format = (
    "%(asctime)s - %(levelname)-8s - %(module)-30s - %(class_name)-25s - "
    "%(function_name)-20s:%(line_number)-4d - %(message)s"
)

# Initialize logging with the basic config
logging.basicConfig(level=logging.INFO)

# Create file and stream handlers
file_handler = logging.FileHandler(log_file_path, mode="a")
stream_handler = logging.StreamHandler()

# Apply the custom formatter to handlers
formatter = CustomFormatter(log_format)
file_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)

# Get the logger and add handlers to it
logger = logging.getLogger(__name__)
logger.addHandler(file_handler)
logger.addHandler(stream_handler)

# Remove the default handlers to avoid duplicate logging
logger.propagate = False

# Test logging
logger.info("Test log entry")


keys_names_list = [
    "header_footer_type",
    "attached_to_filename",
    "parent_id",
    "links",
    "url",
    # 'detection_class_prob',
    "sent_from",
    "page_number",
    # 'coordinates',
    "image_mime_type",
    "document_title",
    #'orig_elements',
    "sent_to",
    "filetype",
    # 'is_continuation', # added recently.
    "emphasized_text_contents",  # added recently.
    "emphasized_text_tags",  # added recently.
    "section",  # added recently.
    "text_as_html",
    "languages",
    "file_directory",
    "filename",
    "file_path" "link_texts",
    "link_urls",
    "page_name",
    "subject",
    "last_modified",
    "section",
    "regex_metadata",
    "image_base64",
    "signature",
    "category_depth",
    "data_source",
    "image_path",
    "detection_origin",
    "acronym_list",
    "key_terms",
    "references",
    "ToC",
    "currentRev",
    "table_category",
    "acronym_keys",
    "acronym_values",
    "use4RAG",
    "plot_code" "clusterID" "tsne_x",
    "tsne_y",
]


def list_files(directory: Path, file_types: list):
    """
    Finds all file paths with extensions matching file_types.
    If multiple identical file paths are found that only differ by their extensions,
    selects only one file path using the list order provided in file_types as the preferred file type.

    Args:
        directory (Path): The directory to search for files.
        file_types (list): List of file extensions to look for.

    Returns:
        list: List of file paths.
    """
    try:
        files = []
        seen = {}
        for file_type in file_types:
            for file in directory.rglob(f"*.{file_type}"):
                base_name = file.stem
                if base_name not in seen:
                    seen[base_name] = file
                    files.append(file)
        return files
    except Exception as e:
        logger.error(f"Error listing files in directory {directory}: {e}")
        return []


def create_directory(path: Path):
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"Failed to create directory {path}: {e}")


def object_to_dict(obj):
    """
    Convert an object's attributes to a dictionary, filtering out private attributes
    and callable methods. It only includes attributes that hold data.

    Args:
    obj: The object from which to extract attributes.

    Returns:
    A dictionary containing attribute names and their values.
    """
    try:
        return {
            attr: getattr(obj, attr)
            for attr in dir(obj)
            if not attr.startswith("__") and not callable(getattr(obj, attr))
        }
    except Exception as e:
        logger.error(f"Error converting object to dict: {e}")
        return {}


def calculate_chunk_params(elements, max_chunk_size):
    # reference https://vectify.ai/blog/LargeDocumentSummarization
    # Sum all characters in elements.page_content
    try:
        # Try to calculate document_size using page_content attribute
        document_size = sum(len(element.text) for element in elements)
    except AttributeError:
        # If there is an AttributeError, try using the text attribute instead
        logger.info(f"'text' attribute is not contained in 'element' object. Using 'page_content' attribute instead")
        document_size = sum(len(element.page_content) for element in elements)

    # Total chunk number
    K = math.ceil(document_size / max_chunk_size)
    # Average integer chunk size
    average_chunk_size = math.ceil(document_size / K)

    return average_chunk_size


def store_elements_to_JSON_file(elements, output_file_path):
    try:
        output_file_path = Path(output_file_path)

        # Ensure the directory exists
        output_file_path.parent.mkdir(parents=True, exist_ok=True)

        with output_file_path.open("w", encoding="utf-8") as file:
            for element in elements:
                # Ensure the original elements are not altered by creating local variables
                text_lines = element.page_content.split("\n")
                non_empty_lines = [line.strip() for line in text_lines if line.strip()]
                text = "\n".join(non_empty_lines)  # Join non-empty lines with a newline character

                metadata = element.metadata.get("filename", "unknown")  # Get filename from metadata or use 'unknown'

                # Create the JSON structure
                data = {"text": text, "meta": {"pile_set_name": metadata}}

                # Write the JSON structure as a line to the file
                file.write(json.dumps(data, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error(f"Error storing elements to JSON file {output_file_path}: {e}")


def extract_title_from_text(text):
    prompt = f"""\
A chunk of text that was extracted from the cover page of a document will be provided to you. \
Read the chunk of extracted text and identify the title of the document. \
The title should contain two parts, the document type and the object the document pertains to. 
Examples of document types: Acceptance Test Procedure, Interface Control Document, System Requirements Document, etc...
Examples of objects: Lowpass Filter Assembly, Multiple-object Tracking Radar, Regulated Power Supply, etc...
Respond with only the title and nothing else."""

    content_1shot = """\
Hardware Design Description\n\nTriple Synthesizer Circuit Card Assembly\n\nPart Number 22011110-1\n\nContract \
Number  (Purchase Order)  ZA015836\n\nDocument Number  HDD22011110\n\nPrepared for:\n\nDRS Internal\n\n2 December 2022\
"""
    response_1shot = """\
Hardware Design Description, Triple Synthesizer Circuit Card Assembly\
"""

    try:
        response = LLM.chat.completions.create(
            model=model_4,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Extracted text: {content_1shot}"},
                {"role": "assistant", "content": f"{response_1shot}"},
                {"role": "user", "content": f"Extracted text: {text}"},
            ],
        )
        title = response.choices[0].message.content.strip()
        return title
    except Exception as e:
        logger.error(f"Error extracting title with GPT-4: {e}")
        return "Unknown Title"


def write_elements_to_text_file(elements, txt_file_path):
    try:
        with open(txt_file_path, "w", encoding="utf-8") as file:
            for doc in elements:
                # Start a section for each document
                file.write("******\nElements Details:\n")

                # Iterate through each attribute of the Document object
                # Assuming Document class has attributes like 'page_content', 'metadata', etc.
                for attr in dir(doc):
                    # Filter out private and special methods/attributes
                    if not attr.startswith("__") and not callable(getattr(doc, attr)):
                        # Special handling for 'metadata' to print each key-value pair
                        if attr == "metadata":
                            file.write(f"{attr}:\n")
                            for key, value in getattr(doc, attr).items():
                                file.write(f"  {key}: {value}\n")
                        else:
                            # For all other attributes, just print the value
                            value = getattr(doc, attr)
                            file.write(f"{attr}: {value}\n")

                # End of document section
                file.write("******\n\n\n")
    except Exception as e:
        logger.error(f"Failed to write text file: {e}")


def compute_embeddings(elements):
    embedder = get_embeddings_model()

    for element in elements:
        if element.page_content:
            embedding = embedder.embed_query(element.page_content)
            element.metadata["embedding"] = embedding
        else:
            element.metadata["embedding"] = ""

    return elements


def process_file(
    file_path: Path,
    base_dir: Path,
    elements_dir: Path,
    json_path: Path,
    max_chunk_size=8000,
    module_logs=False,
    html_summary_prompt=default_html_summary_prompt,
    html_summary_model=default_html_summary_model,
    html_summaries=False,
    input_file: Optional[IO[bytes]] = None,
    input_file_type: Optional[str] = None,
    doc_name: Optional[Path] = None,
):
    if not doc_name:
        base_name = file_path.stem
    else:
        file_path = doc_name
        base_name = doc_name.stem

    images_directory = elements_dir / f"images_{base_name}"
    create_directory(images_directory)
    logger.info(f"Start process_file on {file_path}")

    enable_process_images = False

    if input_file:  # if an input file is provided, don't use 'filename'
        filename = None
        calc_embeddings = True
        enable_process_images = True
    else:
        filename = str(file_path)
        calc_embeddings = False

    try:
        if file_path.suffix == ".pdf":
            logger.info(f"Start partition_pdf")
            elements = partition_pdf(
                file=input_file,
                filename=filename,
                strategy="hi_res",
                languages=["eng"],  # Updated from ocr_languages to languages based on deprecation warning
                extract_images_in_pdf=enable_process_images,
                extract_image_block_output_dir=str(images_directory),
                infer_table_structure=True,
            )
        elif file_path.suffix == ".docx":
            logger.info(f"Start partition_docx")
            elements = partition_docx(
                file=input_file,
                filename=filename,
                infer_table_structure=True,
                include_page_breaks=True,
                include_metadata=True,
                metadata_last_modified=None,
                chunking_strategy=None,
                extract_images=enable_process_images,
            )
        elif file_path.suffix == ".xlsx":
            logger.info(f"Start partition_xlsx")
            elements = partition_xlsx(
                file=input_file,
                filename=filename,
                include_header=True,
                include_metadata=True,
                metadata_last_modified=None,
            )

        logger.info(f"Finished partitioning file")
        # Filter the list to exclude elements with categories "Header" or "Footer"
        elements = [
            element for element in elements if element.category not in ["Header", "Footer", "UncategorizedText"]
        ]
        logger.info(f"removed Header, Footer, and UncategorizedText from elements")
        # Calculate chunk parameters dynamically using character count

        logger.info(f"max_chunk_size: {max_chunk_size}")
        logger.info(f"Element: {elements[0]}")
        average_chunk_size = calculate_chunk_params(elements, max_chunk_size)

        # Ensure non-negative integers for chunk_by_title parameters
        combine_text_under_n_chars = max(0, average_chunk_size // 4)
        max_characters = max(0, average_chunk_size)
        new_after_n_chars = max(0, average_chunk_size - 500)

        if max_characters <= 300:
            if max_characters < 200:
                overlap = 0
            else:
                overlap = round(max_characters * 0.5)
        else:
            overlap = 200

        elements = chunk_by_title(
            elements=elements,
            combine_text_under_n_chars=combine_text_under_n_chars,
            include_orig_elements=True,
            max_characters=max_characters,
            multipage_sections=True,
            new_after_n_chars=new_after_n_chars,
            overlap=overlap,
            overlap_all=False,
        )
        logger.info(f"finished chunk_by_title using avg chunk size:{average_chunk_size}")

        for element in elements:
            # Check if the old attribute 'text' exists
            if hasattr(element, "text"):
                # Set the new attribute 'page_content' with the value from 'text'
                setattr(element, "page_content", getattr(element, "text"))

                # Optionally, remove the old attribute 'text' if no longer needed
                delattr(element, "text")

        # Write GPT-4 responses to a separate text file
        if module_logs == True:
            before_ToC_output_file_path = elements_dir / f"before_ToC__Data.txt"
            write_log_to_file(elements, before_ToC_output_file_path, type="page_content", mode="w", logger=logger)

        if enable_process_images:
            excluded_strings = ["LEONARDO DRS", "DRS", "LEONARDO"]
            process_images(elements, excluded_strings)
            logger.info(f"here:{enable_process_images}")
        logger.info(f"enable_process_images:{enable_process_images}")

        elements = process_large_tables(elements)
        clean_table_of_contents(elements, logger)
        clean_record_of_changes(elements, logger)

        # Iterate through each element in the elements list
        for element in elements:
            if hasattr(element.metadata, "to_dict") and callable(getattr(element.metadata, "to_dict")):
                # Convert metadata using to_dict if available.
                # This converts Unstructured's Document Object to Langchain's Document Object
                element.metadata = element.metadata.to_dict()
            else:
                # Convert metadata manually if no to_dict method is available
                element.metadata = object_to_dict(element.metadata)

            # Ensure all necessary keys are present in metadata
            for key in keys_names_list:
                if key not in element.metadata:
                    element.metadata[key] = None  # or provide a default value appropriate for the key

        if module_logs == True:
            after_output_file_path = elements_dir / f"after__Data.txt"
            write_log_to_file(elements, after_output_file_path, type="page_content", mode="w", logger=logger)

        # generate_embeddings_for_elements(elements)

        # process_elements_based_on_keyword(
        #     elements,
        #     'Embedding_Vector_Sample_ToC.txt',
        #     'ToC',
        #     'contents',
        #     z_threshold:= 2.0,
        #     iqr_multiplier= 1.5
        # )

        # # Replace acronyms in page_content and update metadata with key_terms, then delete elements with acronyms
        elements, acronym_processing_log = process_acronym_text_as_html(elements, logger)

        # Process elements with text_as_html before storing
        elements = llm_summarize_text_as_html(elements, html_summaries=html_summaries, logger=logger)

        if module_logs == True:
            after_output_file_path = elements_dir / f"after__Data.txt"
            write_log_to_file(elements, after_output_file_path, type="page_content", mode="w", logger=logger)

        if elements_dir:
            txt_file_path = elements_dir / f"ElementData_{base_name}.txt"
            write_elements_to_text_file(elements, txt_file_path)

        if json_path:
            output_file_name = Path(json_path) / f"{base_name}.json"
            store_elements_to_JSON_file(elements, output_file_name)

        final_elements = []
        for e in elements:
            if e.metadata["acronym_list"] == None:
                final_elements.append(e)

        logger.info(
            f"Processed {file_path.name}; content written to {elements_dir} and images saved in {images_directory}"
        )

        ## calculate embeddings and add to the elements when calc_embeddings is True (single file bytes were provided to process_file())
        if calc_embeddings:
            elements = compute_embeddings(elements)

        return elements

    except Exception as e:
        logger.error(f"Failed to partition file {file_path}: {e}")

        # Handling DOCX conversion to PDF
        if file_path.suffix == ".docx":
            logger.info(f"Converting {file_path} to PDF file")
            pdf_path = elements_dir / f"{base_name}.pdf"
            try:
                pypandoc.convert_file(str(file_path), "pdf", outputfile=str(pdf_path))
                logger.info(f"Converted DOCX to PDF: {pdf_path}")
                return process_file(pdf_path, base_dir, elements_dir, json_path, max_chunk_size)
            except Exception as convert_error:
                logger.error(f"Failed to convert DOCX to PDF: {convert_error}")

        return []


def get_embeddings_model(embedder_model=default_embedder_model, api_version=default_api_version) -> Embeddings:
    try:
        return AzureOpenAIEmbeddings(model=embedder_model, chunk_size=200, api_version=api_version)
    except Exception as e:
        logger.error(f"Error getting embeddings model: {e}")
        return None


def process_documents(
    WEAVIATE_DOCS_INDEX_NAME,
    doc_directory,
    max_chunk_size=8000,
    elements_directory=None,
    json_dir=None,
    text_key="page_content",
    embedder_model=default_embedder_model,
    html_summary_model=default_html_summary_model,
    html_summary_prompt=default_html_summary_prompt,
    module_logs=False,
    html_summaries=False,
    doc_extensions=["docx", "pdf"],
):
    try:

        # WEAVIATE_DOCS_INDEX_NAME=f"weaviate/{WEAVIATE_DOCS_INDEX_NAME}"

        if isinstance(doc_directory, list):
            potential_files = [Path(file) for file in doc_directory]
        else:
            doc_directory = Path(doc_directory)
            if doc_directory.is_file():
                potential_files = [doc_directory]
            elif doc_directory.is_dir():
                potential_files = list_files(doc_directory, doc_extensions)  # ["docx", "pdf"])#, "txt"])
            else:
                raise ValueError("Invalid doc_directory value")

        record_manager = ExtendedSQLRecordManager(
            f"weaviate/{WEAVIATE_DOCS_INDEX_NAME}", db_url=RECORD_MANAGER_DB_URL, logger=logger
        )

        # Get the status of potential files
        new_files = []
        modified_files = []
        current_files = []

        for file in potential_files:
            status = record_manager.get_document_status(str(file))
            if status == "new":
                new_files.append(file)
            elif status == "modified":
                modified_files.append(file)
            elif status == "current":
                current_files.append(file)

        logger.info(f"New files: {len(new_files)}")
        logger.info(f"Modified files: {len(modified_files)}")
        logger.info(f"Current files: {len(current_files)}")

        logger.info(f"Processing {len(new_files) + len(modified_files)} out of {len(potential_files)} documents.")

        files_to_process = new_files + modified_files
        file_info = []
        for idx, file in enumerate(files_to_process):
            current_elements_dir = elements_directory if not isinstance(elements_directory, list) else None
            current_json_dir = json_dir if not isinstance(json_dir, list) else None

            if isinstance(elements_directory, list):
                current_elements_dir = elements_directory[idx]
            if isinstance(json_dir, list):
                current_json_dir = json_dir[idx]

            file_info.append((file, file.parent, Path(current_elements_dir), current_json_dir))

        for batch_start in range(0, len(file_info), DOCUMENT_BATCH_SIZE):
            batch = file_info[batch_start : batch_start + DOCUMENT_BATCH_SIZE]

            with ThreadPoolExecutor(max_workers=DOCUMENT_PROCESS_THREADS) as executor:
                results = list(
                    executor.map(
                        lambda args: process_file(
                            args[0],
                            args[1],
                            args[2],
                            args[3],
                            max_chunk_size,
                            module_logs,
                            html_summary_prompt,
                            html_summary_model,
                            html_summaries,
                        ),
                        batch,
                    )
                )

            elements = [item for sublist in results for item in sublist]

            if not elements:
                logger.info("No elements to ingest for this batch.")
                continue

            for element in elements:
                file_directory = element.metadata.get("file_directory")
                filename = element.metadata.get("filename")

                if file_directory is not None and filename is not None:
                    element.metadata["file_path"] = str(Path(file_directory) / filename)
                else:
                    logger.warning(f"Missing file_directory or filename in element metadata: {element.metadata}")

            ingest_docs(
                elements,
                record_manager,
                WEAVIATE_DOCS_INDEX_NAME,
                text_key=text_key,
                embedder_model=embedder_model,
                html_summary_model=html_summary_model,
                html_summary_prompt=html_summary_prompt,
                max_chunk_size=max_chunk_size,
                module_logs=module_logs,
                html_summaries=html_summaries,
            )

    except Exception as e:
        logger.error(f"Error processing documents: {e}")


def ingest_docs(elements, record_manager, INDEX_NAME, **kwargs):
    try:

        # for element in elements:
        #     element.metadata['url'] = r"https://aisfwb.empower.drs.com/Apps/OpenDocument.aspx?obj=0&docid=615460"

        filtered_elements = []
        acronym_keys = []
        acronym_values = []
        document_map_acronym = []

        for element in elements:
            element.metadata["use4RAG"] = True
            element.metadata["plot_code"] = 1
            element.metadata["clusterID"] = -1
            element.metadata["tsne_x"] = 0.0001
            element.metadata["tsne_y"] = 0.0001

        for element in elements:
            if not element.metadata.get("acronym_list"):
                filtered_elements.append(element)
            else:
                acronym = element.metadata.get("acronym_list", {})
                keys = list(acronym.keys())
                values = list(acronym.values())
                mapping = element.metadata.get("file_path", "")
                acronym_keys.append(keys)
                acronym_values.append(values)
                document_map_acronym.append(mapping)

        elements = filtered_elements

        for element in elements:
            file_path = element.metadata.get("file_path", "")
            if file_path in document_map_acronym:
                index = document_map_acronym.index(file_path)
                element.metadata["acronym_keys"] = acronym_keys[index]
                element.metadata["acronym_values"] = acronym_values[index]

        # # Define the connection parameters
        # connection_params = ConnectionParams(
        #     http=ProtocolParams(
        #         host="localhost",  # Change this to your Weaviate host if different
        #         port=8080,         # Change this to your Weaviate port if different
        #         secure=False       # Set to True if using HTTPS
        #     ),
        #     grpc=ProtocolParams(
        #         host="localhost",  # Change this to your Weaviate host if different
        #         port=50051,         # Change this to your Weaviate gRPC port if different
        #         secure=False       # Set to True if using HTTPS
        #     )
        # )

        # Create the client
        client = weaviate.Client(
            url=WEAVIATE_URL,
            auth_client_secret=AuthApiKey(api_key=WEAVIATE_API_KEY),
        )

        text_key = kwargs.get("text_key", "page_content")
        embedder_model = kwargs.get("embedder_model")

        # Tokenization overrides with tuples (key, datatype, tokenization)
        tokenization_overrides = {
            "filename": ("text", "field"),
            "document_title": ("text", "field"),
            "key_terms": ("text[]", "word"),
            "link_texts": ("text[]", "word"),
            "link_urls": ("text[]", "word"),
            "acronym_list": (None, None),
            "acronym_keys": ("text[]", "word"),
            "acronym_values": ("text[]", "word"),
            "use4RAG": ("boolean", None),
        }

        schema_keys_names_list = create_weaviate_schema(
            client, INDEX_NAME, text_key, elements, tokenization_overrides, logger=logger
        )

        # Create the vector store object
        vectorstore = Weaviate(
            client=client,
            index_name=INDEX_NAME,
            text_key=text_key,
            embedding=get_embeddings_model(embedder_model),
            by_text=False,
            attributes=schema_keys_names_list,
        )

        indexing_stats = record_manager.add_document(
            elements,
            vectorstore,
            # cleanup="full",
            force_update=(os.environ.get("FORCE_UPDATE") or "false").lower() == "true",
            batch_size=kwargs.get("batch_size", 1000),
            **kwargs,
        )
        logger.info(f"Indexing stats: {indexing_stats}")

    except Exception as e:
        logger.error(f"Error ingesting documents: {e}")


def main():
    try:
        dir_path = r"docs"  # r"H:\\SEP-04 Project Engineering\\SEP-04-01(M) Process for Product Development.docx"#r"C:\Users\Steve.Long\Documents\2201 BOM scrub (5-17-22).xlsx"#r"L:\papers"#G:\Unstructured_Processing\JACSKE_Program_10000_Chunks"#H:\SEP-04 Project Engineering"#H:\\SEP-04 Project Engineering\\SEP-04-01(M) Process for Product Development.docx" #H:\SEP-04 Project Engineering"#
        store_dir = r"elements_dir"
        process_documents(
            WEAVIATE_DOCS_INDEX_NAME="test_22040712f",
            max_chunk_size=10000,
            doc_directory=dir_path,
            elements_directory=store_dir,
            json_dir=store_dir,
            module_logs=False,
            html_summaries=False,
            doc_extensions=["docx", "pdf"],  # , "xlsx"]
        )
    except Exception as e:
        logger.error(f"Error in main function: {e}")


if __name__ == "__main__":
    main()
