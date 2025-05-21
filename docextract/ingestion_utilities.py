
import os
import logging
from typing import Dict
import json
from bs4 import BeautifulSoup

from langchain_openai import AzureOpenAIEmbeddings, AzureOpenAI
from langchain_core.embeddings import Embeddings
import base64

default_api_version = os.getenv("AZURE_OPENAI_API_VERSION")
model_4 = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
default_html_summary_model = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
default_embedder_model = os.getenv("AZURE_OPENAI_EMBEDDER")

def get_embeddings_model(embedder_model=default_embedder_model, api_version=default_api_version) -> Embeddings:
    try:
        return AzureOpenAIEmbeddings(model=embedder_model, chunk_size=200, api_version=api_version)
    except Exception as e:
        print(f"Error getting embeddings model: {e}")
        return None

def get_llm(model=model_4, api_version=default_api_version):
    try:
        return AzureOpenAI(model=model, azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"), api_key=os.getenv("AZURE_OPENAI_API_KEY"), api_version=api_version)
    except Exception as e:
        print(f"Error getting LLM model: {e}")
        return None

def log_and_delete_element(element, logger: logging.Logger):
    try:
        logger.info(f"Deleting element {id(element)} from filename:{element.metadata['filename']}")
        logger.info(f"Element contents: {element.page_content[:200]}")
        logger.info(f"Element metadata: {element.metadata['text_as_html'][:200]}")
        
        print(f"Deleting element {id(element)} in filename:{element.metadata['filename']}")

    except Exception as e:
        try:
            logger.info(f"Deleting element {id(element)} from filename:{element.metadata.filename}")
            logger.info(f"Element contents: {element.page_content[:200]}")
            logger.info(f"Element metadata: {element.metadata.text_as_html[:200]}")
        
            print(f"Deleting element {id(element)} in filename:{element.metadata.filename}")


        except Exception as e:
            logger.error(f"Error logging element: {e}")

def write_log_to_file(log_data, file_path, logger: logging.Logger=None, type=None, mode='w'):
    
    try:
        if type == None:
            with open(file_path, mode, encoding='utf-8') as file:
                for response in log_data:
                    file.write(json.dumps(response, ensure_ascii=False) + '\n')

        elif type == 'page_content':
            with open(file_path, mode, encoding='utf-8') as file:
                for element in log_data:
                    page_content = element.page_content
                    file.write(page_content + '\n')

        elif type == 'text_as_html':
            with open(file_path, mode, encoding='utf-8') as file:
                for element in log_data:
                    text_as_html = element.metadata['text_as_html']
                    file.write(text_as_html + '\n')

        else:
            logger.error(f"In function write_log_to_file, 'type = {type}' is not valid. Log not stored to file {file_path}")

    except Exception as e:
        logger.error(f"Error writing log data to file {file_path}: {e}")


def clean_table_of_contents(elements, logger = None):
    """
    Iterates through a list of elements to clean up Table of Contents.

    :param elements: List of elements to process.
    """
    # for element in elements:
    #     # Check if the old attribute 'text' exists
    #     if hasattr(element, 'text'):
    #         # Set the new attribute 'page_content' with the value from 'text'
    #         setattr(element, 'page_content', getattr(element, 'text'))
            
    #         # Optionally, remove the old attribute 'text' if no longer needed
    #         delattr(element, 'text')

    try:
        
        # def normalize_whitespace(text):
        #     return ' '.join(text.split())
        log_delete = False

        for element in elements:
            if 'table of contents' in element.page_content.lower():                
                if hasattr(element.metadata, 'orig_elements') and element.metadata.orig_elements:
                    lines_to_delete = []
                    collecting = False
                    element_to_keep = []
                    for orig_elem in element.metadata.orig_elements:

                        if hasattr(orig_elem, 'text') and 'table of contents' in orig_elem.text.lower():
                            collecting = True
                        if collecting:
                            if hasattr(orig_elem, 'text'):
                                lines_to_delete.append(orig_elem.text)
                                log_delete = True
                            if orig_elem.category == 'PageBreak':
                                collecting = False
                        elif orig_elem.category == 'PageBreak':
                            element_to_keep.append('')
                        else:
                            element_to_keep.append(orig_elem.text)
                    
                    # Join lines_to_delete into a single string and normalize whitespace
                    element_to_keep_str = '\n\n'.join(element_to_keep)
                    
                    element.page_content = element_to_keep_str

                    if log_delete == True:
                        logger.info(f"Table of Contents found in file{element.metadata.filename}. Removing table from document chunks")
                       
                    return
    
    except Exception as e:
        return
    


def clean_record_of_changes(elements, logger=None):
    """
    Iterates through a list of elements to clean up Record of Change or Revision History.

    :param elements: List of elements to process.
    """
    try:
        if elements is None:
            raise ValueError("The 'elements' parameter is None.")

        element_to_keep = []
        table_found = False
        for element in elements:
            if hasattr(element.metadata, 'text_as_html') and element.metadata.text_as_html is not None:
                text_as_html = element.metadata.text_as_html

                if not table_found:  # assuming there is only one revision table
                    if 'record of changes' in text_as_html.lower() or 'revision history' in text_as_html.lower():
                        table_found = True
                        # log_and_delete_element(element, logger)
                        if logger:
                            logger.info(f"Revision history table found in file {element.metadata.filename}. Removing table from document chunks")
                    else:
                        element_to_keep.append(element)
                else:
                    element_to_keep.append(element)
            else:
                element_to_keep.append(element)

        if table_found:
            elements = element_to_keep
            return elements

        # Plan B - Revision table not found. Check again for revision history but not in a table
        log_delete = False
        for element in elements:
            if 'record of changes' in element.page_content.lower() or 'revision history' in element.page_content.lower():
                if hasattr(element.metadata, 'orig_elements') and element.metadata.orig_elements is not None:
                    lines_to_delete = []
                    collecting = False
                    element_to_keep = []
                    for orig_elem in element.metadata.orig_elements:
                        if hasattr(orig_elem, 'text') and ('record of changes' in orig_elem.text.lower() or 'revision history' in orig_elem.text.lower()):
                            collecting = True
                        if collecting:
                            if hasattr(orig_elem, 'text'):
                                lines_to_delete.append(orig_elem.text)
                                log_delete = True
                            if orig_elem.category == 'PageBreak':
                                collecting = False
                        elif orig_elem.category == 'PageBreak':
                            element_to_keep.append('')
                        else:
                            element_to_keep.append(orig_elem.text)

                    # Join lines_to_delete into a single string and normalize whitespace
                    element_to_keep_str = '\n'.join(element_to_keep)
                    element.page_content = element_to_keep_str

                    if log_delete and logger:
                        logger.info(f"Revision history found in file {element.metadata.filename}. Removing table from document chunks")

                    return elements

    except Exception as e:
        if logger:
            logger.error(f"An error occurred: {str(e)}")
        return


def process_table(html_content: str) -> Dict[str, str]:
    """
    Extract dictionary list from HTML table content.

    :param html_content: HTML content containing the table.
    :return: Dictionary of acronyms and their meanings.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    table = soup.find('table')

    table_dict = {}
    if table:
        for row in table.find_all('tr')[1:]:  # Skip the header row
            cells = row.find_all('td')
            if len(cells) == 2:
                first_column = cells[0].get_text(strip=True)
                second_column = cells[1].get_text(strip=True)
                table_dict[first_column] = second_column
    return table_dict

def combine_text_as_html(elements):

    
    text_as_html = elements[0].metadata.text_as_html
    for element in elements:
        text_as_html = f"{text_as_html}\n{element.metadata.text_as_html}"

    elements[0].metadata.text_as_html = text_as_html
    return elements[0]

def mostly_contains(text, substrings, threshold=0.6):
    """Check if any substring constitutes at least `threshold` percent of the text."""
    text_length = len(text)
    if text_length == 0:
        return False  # Avoid division by zero
    
    for substr in substrings:
        if text.count(substr) * len(substr) >= threshold * text_length:
            return True
    return False

def process_images(elements,excluded_strings=None):
    for e in elements:
        image_base64 = []
        for orig in e.metadata.orig_elements:
            if orig.category == "Image" and not mostly_contains(orig.text, excluded_strings):
                image_path = orig.metadata.image_path
                if image_path and os.path.exists(image_path):
                    with open(image_path, "rb") as f:
                        image_base64.append(base64.b64encode(f.read()).decode("utf-8"))
                    
                    # Delete the original file after processing
                    try:
                        os.remove(image_path)
                        print(f"Deleted: {image_path}")
                    except Exception as err:
                        print(f"Error deleting {image_path}: {err}")
        if image_base64:
            e.metadata.image_base64 = image_base64

def process_large_tables(elements, logger=None):
    try:
        table_found = False
        combine_tables = False
        table_to_combine = []
        new_elements = []

        for element in elements:
            if element.category == 'Table':
                if not table_found:
                    table_found = True
                    table_to_combine = [element]
                elif element.metadata.is_continuation:
                    table_to_combine.append(element)
                    combine_tables = True
                elif combine_tables:
                    temp = combine_text_as_html(table_to_combine)
                    new_elements.append(temp)
                    table_to_combine = [element]
                    table_found = True
                    combine_tables = False
                else:
                    new_elements.extend(table_to_combine)
                    table_to_combine = [element]
            elif table_found:
                if combine_tables:
                    temp = combine_text_as_html(table_to_combine)
                    new_elements.append(temp)
                else:
                    new_elements.extend(table_to_combine)
                table_found = False
                combine_tables = False
                table_to_combine = []
                new_elements.append(element)
            else:
                new_elements.append(element)

        # If there is a remaining table to combine at the end of the loop
        if table_to_combine:
            if combine_tables:
                temp = combine_text_as_html(table_to_combine)
                new_elements.append(temp)
            else:
                new_elements.extend(table_to_combine)

        elements = new_elements

    except Exception as e:
        if logger:
            logger.info(f"Error occurred during 'process_large_tables' for file: {element.metadata.filename}. Exception: {e}")
        else:
            print(f"Error occurred during 'process_large_tables' for file: {element.metadata.filename}. Exception: {e}")

    return elements
