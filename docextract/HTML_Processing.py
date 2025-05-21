
import os
import logging
import json
from typing import List, Tuple, Any, Dict
from bs4 import BeautifulSoup
import numpy as np
from ingestion_utilities import get_embeddings_model
from sklearn.metrics.pairwise import cosine_similarity
from openai import AzureOpenAI

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception as e:
    print(f"Error loading environment variables: {e}")

# Set environment variables
os.environ['CUDA_VISIBLE_DEVICES'] = '0'
os.environ['LOCAL_FILES_ONLY'] = 'True'
os.environ['TRANSFORMERS_OFFLINE'] = 'True'
os.environ['HF_HUB_OFFLINE'] = 'True'

WEAVIATE_URL = os.environ["WEAVIATE_URL"]
WEAVIATE_API_KEY = os.environ["WEAVIATE_API_KEY"]
RECORD_MANAGER_DB_URL = os.getenv('RECORD_MANAGER_DB_URL')

default_api_version = os.getenv("AZURE_OPENAI_API_VERSION")
model_4 = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
default_html_summary_model = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
default_embedder_model = os.getenv("AZURE_OPENAI_EMBEDDER")

# LLM = get_llm(model=model_4)
LLM = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"), 
    api_key=os.getenv("AZURE_OPENAI_API_KEY"), 
    api_version=default_api_version
)

embeddings_client=get_embeddings_model(default_embedder_model)


# Default prompts
default_html_summary_prompt = "Your task is to summarize the HTML content provided to you. This HTML represents content extracted from a .docx file using Unstructured-IO libraries. Respond with a concise summary of the content."

html_1shota = """<html>
<head>
    <title>Example Document</title>
</head>
<body>
    <h1>Document Title</h1>
    <p>This is an example paragraph that provides some content about the document. It includes several sentences that give a brief overview of the document's topic.</p>
</body>
</html>"""

html_1shotb = "The example document is about a general topic and includes an overview and some details."

html_prompt = """Your task is to categorize the HTML content provided to you. This HTML represents content \
extracted from a .docx file using Unstructured-IO libraries. Your response must be one of the following categories:
1) Appendix
2) Table of Contents
3) References
4) Other

Respond with the category number and the appropriate JSON format:

1. Appendix:
{
    "category": 1,
    "acronyms": {
        "acronym1": "Acronym Definition",
        "acronym2": "Acronym Definition",
        "acronym3": "Acronym Definition"
    }
}

2. Table of Contents:
{
    "category": 2,
    "sections": ["section 1", "section 2", "section 3"]
}

3. References:
{
    "category": 3,
    "reference_list": ["reference1 document number", "reference2 document number", "reference3 document number"]
}

4. Other:
{
    "category": 4
}"""

def test_acronym_extraction(acronym_dict: Dict[str, str], threshold: float = 0.55) -> Tuple[bool, str]:
    """
    Validate the extracted acronym dictionary based on a percentage threshold.

    :param acronym_dict: Dictionary of acronyms and their meanings.
    :param threshold: Percentage threshold for validation (default is 55%).
    :return: Tuple containing a boolean indicating validity and a validation message.
    """
    if not acronym_dict:
        return False, "The dictionary is empty."
    
    total_pairs = len(acronym_dict)
    valid_pairs = sum(
        key.replace('-', '').replace(' ', '').isalnum() and isinstance(value, str) and bool(value) 
        for key, value in acronym_dict.items()
    )
    
    if total_pairs == 0:
        return False, "The dictionary is empty."
    
    valid_percentage = valid_pairs / total_pairs
    
    if valid_percentage >= threshold:
        return True, "The acronym list has been extracted correctly."
    else:
        return False, f"The acronym list did not meet the {threshold * 100}% validity threshold. Validity: {valid_percentage * 100:.2f}%"

def process_acronym_table(html_content: str) -> Dict[str, str]:
    """
    Extract acronym list from HTML table content.

    :param html_content: HTML content containing the table.
    :return: Dictionary of acronyms and their meanings.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    table = soup.find('table')

    acronym_dict = {}
    if table:
        for row in table.find_all('tr')[1:]:  # Skip the header row
            cells = row.find_all('td')
            if len(cells) == 2:
                acronym = cells[0].get_text(strip=True)
                meaning = cells[1].get_text(strip=True)
                acronym_dict[acronym] = meaning
    return acronym_dict

# def embed_text(text: str) -> np.ndarray:
#     """
#     Embed the given text using OpenAI's Ada model.

#     :param text: Text to be embedded.
#     :return: Numpy array containing the embedding.
#     """

    
    
#     # response = LLM.embeddings.create(input=text, model=default_embedder_model)
#     return embeddings_client.embed_query(text)#np.array(response['data'][0]['embedding'])

# def categorize_content_with_embeddings(elements: List[Any], threshold: float = 0.85) -> None:
#     """
#     Categorize HTML content using embeddings and cosine similarity.

#     :param elements: List of elements containing metadata and content.
#     :param threshold: Cosine similarity threshold for categorization.
#     """
#     contents_elements = [el for el in elements if 'contents' in el.metadata.get('text_as_html', '').lower()]
#     if not contents_elements:
#         return

#     embeddings = np.array([embed_text(el.metadata['text_as_html']) for el in contents_elements])
#     centroid = np.mean(embeddings, axis=0)
    
#     similarities = cosine_similarity(embeddings, centroid.reshape(1, -1))
#     for el, sim in zip(contents_elements, similarities):
#         if sim >= threshold:
#             el.metadata['category'] = 2  # Tag as Table of Contents

def process_html_element(element: Any, logger: logging.Logger) -> Dict[str, Any]:
    """
    Process a single HTML element.

    :param element: Element containing metadata and content.
    :param logger: Logger for logging information and errors.
    :return: Processed element metadata and content.
    """
    html_content = element.metadata.get('text_as_html', None)
    page_content = element.page_content

    if html_content is not None:
        soup = BeautifulSoup(html_content, 'html.parser')
        visible_texts = soup.stripped_strings
        visible_text = ' '.join(visible_texts)
        
        if visible_text.strip():
            table_dict = process_acronym_table(html_content)
            is_valid, validation_message = test_acronym_extraction(table_dict)

            if is_valid:
                element.metadata['acronym_list'] = table_dict
                logger.info(f"Extracted acronym list for element {id(element)} in {element.metadata['filename']}")
            else:
                logger.info(f"Acronym check failed for element {id(element)} in {element.metadata['filename']}, using embeddings for categorization")
                # Embed and categorize content as Table of Contents if applicable
                categorize_content_with_embeddings([element])
        
        elif not page_content.strip():
            logger.warning(f"page_content is empty and html contains no visible text in text_as_html metadata for element {id(element)} in {element.metadata['filename']}")
            # log_and_delete_element(element, logger)
            
    elif not page_content.strip():
        logger.warning(f"page_content is empty and no text_as_html metadata for element {id(element)} in {element.metadata['filename']} - Deleting element")
        # log_and_delete_element(element, logger)

    return element.metadata

def process_text_as_html(
        elements: List[Any], 
        html_summaries: bool = False,
        html_prompt: str = default_html_summary_prompt, 
        html_model: str = default_html_summary_model, 
        html_1shota: str = html_1shota,
        html_1shotb: str = html_1shotb,
        logger: logging.Logger = None
        ) -> Tuple[List[Any], List[Dict[str, Any]]]:
    
    logger = logger if logger else logging.getLogger(__name__)
    
    html_processing_output = []
    new_elements = []

    logger.info(f"Starting process_text_as_html for {elements[0].metadata['filename']} with {len(elements)} elements")

    for element in elements:
        try:
            processed_metadata = process_html_element(element, logger)
            if element.page_content.strip():
                new_elements.append(element)
            html_processing_output.append(processed_metadata)
        except Exception as e:
            logger.error(f"Error processing HTML for element {id(element)} in {element.metadata['filename']}: {e}")

    logger.info(f"Finished process_text_as_html with {len(new_elements)} elements and {len(html_processing_output)} GPT-4 responses")
    return new_elements, html_processing_output


def embed_text(text: str) -> np.ndarray:
    """
    Embed the given text using OpenAI's Ada model.

    :param text: Text to be embedded.
    :return: Numpy array containing the embedding.
    """
    return embeddings_client.embed_query(text)

def generate_embeddings_for_elements(elements: List[Any]) -> None:
    """
    Generate embeddings for all elements and store them in element.embeddings.

    :param elements: List of elements to generate embeddings for.
    """
    try:
        for element in elements:
            page_content = element.page_content
            text_as_html = element.metadata.get('text_as_html', '')

            if page_content.strip() or text_as_html.strip():
                element.embeddings = embed_text(f"{page_content}\n{text_as_html}")
    except Exception as e:       
        print(f"Failed to get embedding for element {id(element)} in {element.metadata['filename']}: {e}")
 

def categorize_content_with_embeddings(elements: List[Any], threshold: float = 0.85) -> None:
    """
    Categorize HTML content using embeddings and cosine similarity.

    :param elements: List of elements containing metadata and content.
    :param threshold: Cosine similarity threshold for categorization.
    """
    contents_elements = [el for el in elements if 'contents' in el.metadata.get('text_as_html', '').lower()]
    if not contents_elements:
        return

    embeddings = np.array([el.embeddings for el in contents_elements])
    centroid = np.mean(embeddings, axis=0)
    
    similarities = cosine_similarity(embeddings, centroid.reshape(1, -1))
    for el, sim in zip(contents_elements, similarities):
        if sim >= threshold:
            el.metadata['category'] = 2  # Tag as Table of Contents

def process_elements_based_on_keyword(elements: List[Any], file_path: str, category: str, keyword: str, 
                                      z_threshold: float = 2.0, iqr_multiplier: float = 1.5) -> None:
    """
    Process elements to find those containing a keyword and calculate similarity scores.

    :param elements: List of elements to process.
    :param file_path: Path to the .txt file containing the reference embedding.
    :param category: Category string to store in element.metadata['table_category'].
    :param keyword: Keyword or phrase to search for in elements.
    :param z_threshold: Z-score threshold to consider a value as an outlier.
    :param iqr_multiplier: Multiplier for the IQR method to consider a value as an outlier.
    """
    with open(file_path, 'r') as file:
        reference_embedding = np.fromstring(file.read().strip(), sep=' ')
    
    keyword_lower = keyword.lower()
    matching_elements = [
        el for el in elements 
        if (el.page_content and keyword_lower in el.page_content.lower()) 
        or (el.metadata.get('text_as_html') and keyword_lower in el.metadata['text_as_html'].lower())
    ]
    
    if not matching_elements:
        return
    
    matching_similarities = []
    for element in matching_elements:
        matching_similarity = cosine_similarity([element.embeddings], [reference_embedding])[0][0]
        matching_similarities.append(matching_similarity)

    similarities = []
    for element in elements:
        similarity = cosine_similarity([element.embeddings], [reference_embedding])[0][0]
        similarities.append(similarity)       
    
    highest_similarity = max(matching_similarities)
    best_element = matching_elements[matching_similarities.index(highest_similarity)]
    
    mean_score = np.mean(similarities)
    std_dev_score = np.std(similarities)
    
    if std_dev_score == 0:
        z_score = 0
    else:
        z_score = (highest_similarity - mean_score) / std_dev_score
    
    Q1 = np.percentile(similarities, 25)
    Q3 = np.percentile(similarities, 75)
    IQR = Q3 - Q1
    lower_bound = Q1 - iqr_multiplier * IQR
    upper_bound = Q3 + iqr_multiplier * IQR
    
    is_outlier_z = abs(z_score) > z_threshold
    is_outlier_iqr = highest_similarity < lower_bound or highest_similarity > upper_bound
    
    if is_outlier_iqr or is_outlier_z:
        best_element.metadata['table_category'] = category



def load_strings_from_json(file_path: str) -> List[str]:
    """
    Load strings to embed from a JSON file.

    :param file_path: Path to the JSON file.
    :return: List of strings to embed.
    """
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data.get('strings', [])

def clean_text(text: str) -> str:
    """
    Clean the text by handling newlines, extra spaces, and other common text issues.

    :param text: Text to be cleaned.
    :return: Cleaned text.
    """
    # Replace multiple newlines with a single space
    text = text.replace('\r', ' ').replace('\n', ' ')
    # Replace tabs with a single space
    text = text.replace('\t', ' ')
    # Replace multiple spaces with a single space
    text = ' '.join(text.split())
    return text

def create_and_store_aggregated_embedding(file_path: str, output_path: str, method: str = 'average', weights: List[float] = None) -> None:
    """
    Create embeddings for a list of strings from a JSON file, aggregate them using the specified method, and store the vector in a text file.

    :param file_path: Path to the JSON file containing the strings to be embedded.
    :param output_path: Path to the text file where the aggregated embedding will be stored.
    :param method: Method to use for aggregation ('average', 'max_pooling', 'min_pooling', 'weighted_average').
    :param weights: Weights for weighted averaging (optional, required if method is 'weighted_average').
    """
    strings_to_embed = load_strings_from_json(file_path)
    cleaned_strings = [clean_text(string) for string in strings_to_embed]
    embeddings = np.array([embed_text(string) for string in cleaned_strings])
    
    if method == 'average':
        aggregated_embedding = np.mean(embeddings, axis=0)
    elif method == 'max_pooling':
        aggregated_embedding = np.max(embeddings, axis=0)
    elif method == 'min_pooling':
        aggregated_embedding = np.min(embeddings, axis=0)
    elif method == 'weighted_average':
        if weights is None:
            raise ValueError("Weights must be provided for weighted averaging.")
        aggregated_embedding = np.average(embeddings, axis=0, weights=weights)
    else:
        raise ValueError("Unsupported aggregation method.")

    with open(output_path, 'w') as file:
        file.write(' '.join(map(str, aggregated_embedding)))



def extract_title_from_text(text, logger=None):
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
                {"role": "user", "content": f"Extracted text: {text}"}
            ]
        )
        title = response.choices[0].message.content.strip()
        return title
    except Exception as e:
        logger.error(f"Error extracting title with GPT-4: {e}")
        return "Unknown Title"

def llm_summarize_text_as_html(
        elements, 
        html_summaries=False,
        html_summary_prompt=default_html_summary_prompt, 
        html_summary_model=default_html_summary_model, 
        max_chunk_size = 8000,
        logger = None
        ):
    html_processing_output = []

    logger.info(f"Starting process_text_as_html for {elements[0].metadata['filename']} with {len(elements)} elements ")
    try:
        doc_title = None
        if html_summaries is True:
            doc_title = extract_title_from_text(elements[0].page_content)

            new_html_summary_prompt= f"""\
    Your task is to provide a detailed, semantically relevant description of the provided HTML. \
    This HTML represents content extracted from a .docx file titled {doc_title} using Unstructured-IO libraries. \
    Your description will be converted into a vector embedding for semantic search purposes.

    Ensure your description encapsulates unique terms, column/row names, categories, table data, titles, \
    labels, and other key information. Minimize common, generic characteristics and focus on details that \
    highlight the uniqueness of the content. 

    Your description shall be no more than 1000 words.

    If the HTML lacks semantic content (e.g., empty tags, whitespace, \
    purely structural or decorative elements), respond with 'None.' 

    Write descriptions as if viewing the original content, not the HTML. Speak directly to the content \
    without prefacing with phrases like 'The HTML content represents.' The reader should not be aware that \
    the text was extracted or converted to HTML.
    """

            new_html_content_1shot="""<table>
    <thead>
    <tr><th>Voltage  </th><th>Max Current  </th><th>Current Limit  </th></tr>
    </thead>
    <tbody>
    <tr><td>22 V ±10%</td><td>5 A          </td><td>7 A            </td></tr>
    </tbody>
    </table>"""

            new_html_summary_1shot="""\
    The table presents electrical specifications for a device, listing voltage, maximum current, \
    and current limit. The voltage is specified as 22 volts with a tolerance of plus or minus 10%. \
    The maximum current is 5 amperes, and the current limit is 7 amperes.\
    """



        for element in elements:
            text_as_html = element.metadata.get('text_as_html', None)
            page_content = element.page_content
            if not page_content:
                page_content = ''

            if text_as_html is not None:
                html_content = text_as_html
                soup = BeautifulSoup(html_content, 'html.parser')
                visible_texts = soup.stripped_strings  # Extract visible text
                visible_text = ' '.join(visible_texts)
                
                if visible_text.strip():
                    if html_summaries is True:
                        try:

                            # Use GPT-4 to generate a summary
                            response = LLM.chat.completions.create(
                                model=html_summary_model, 
                                messages=[
                                    {"role": "system", "content": f"{new_html_summary_prompt}"},
                                    {"role": "user", "content": f"{new_html_content_1shot}"},
                                    {"role": "assistant", "content": f"{new_html_summary_1shot}"},
                                    {"role": "user", "content": f"{page_content}\n{text_as_html}"},
                                ]
                            )
                            summary = response.choices[0].message.content.strip()
                            element.page_content = summary

                            # Store response for later use
                            html_processing_output.append({
                                "element_id": id(element),
                                "file_name": element.metadata['filename'],
                                "file_directory": element.metadata['file_directory'], 
                                "page_name": element.metadata['page_name'], 
                                "page_content": element.page_content,
                                "processed_html_used_for_logic": soup,
                                "html_content": html_content,
                                "summary": summary,
                                "document_title": doc_title
                            })
                            print(f"Generated summary for element {id(element)} in {element.metadata['filename']} \n\tSummary: {summary[:80]}...")
                            logger.info(f"Generated summary for element {id(element)} in {element.metadata['filename']} \n\tSummary: {summary[:80]}...")
                        except Exception as e:
                            logger.error(f"Error processing HTML with GPT-4 for element {id(element)} in {element.metadata['filename']}: {e}")
                            print(f"Error processing HTML with GPT-4 for element {id(element)} in {element.metadata['filename']}: {e}")
                    else:
                        html_processing_output.append({
                            "element_id": id(element),
                            "file_name": element.metadata['filename'],
                            "file_directory": element.metadata['file_directory'], 
                            "page_name": element.metadata['page_name'], 
                            "page_content": element.page_content,
                            "processed_html_used_for_logic": soup,
                            "html_content": html_content,
                            "summary": None,
                            "document_title": doc_title
                        })
                elif not page_content.strip():
                    print(f"page_content is empty and html contains no visible text in text_as_html metadata for element {id(element)} in {element.metadata['filename']}")
                    logger.warn(f"page_content is empty and html contains no visible text in text_as_html metadata for element {id(element)} in {element.metadata['filename']}")
                    # log_and_delete_element(element)
                    
            elif not page_content.strip():
                print(f"page_content is empty and no text_as_html metadata for element {id(element)} in {element.metadata['filename']} - Deleting element")
                logger.warn(f"page_content is empty and no text_as_html metadata for element {id(element)} in {element.metadata['filename']} - Deleting element")
                # log_and_delete_element(element)

            element.metadata['document_title'] = doc_title

        logger.info(f"Finished process_text_as_html with {len(elements)} elements and {len(html_processing_output)} GPT-4 responses")
        
        
        return elements

    except Exception as e:
        logger.error(f"Error in llm_summarize_text_as_html.")
        return
