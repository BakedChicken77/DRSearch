
import re
import logging
from typing import List, Tuple, Any, Dict
from bs4 import BeautifulSoup



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
    valid_pairs = 0
    invalid_entries = []


    check_invalid_entries = []
    seen_keys = set()

    for key, value in acronym_dict.items():
        if not isinstance(key, str) or not isinstance(value, str):
            invalid_entries.append((key, value))
        
        # Check if the value is not empty or just whitespace
        if not bool(value.strip()):
            invalid_entries.append((key, value))
 
        # Extract capital letters from the definition
        capital_letters = ''.join(char for char in value if char.isupper())
        
        # Check if the acronym letters are in order within the capital letters
        it = iter(capital_letters)
        if not all(char in it for char in key):
            check_invalid_entries.append((key, value))

    if total_pairs == 0:
        return False, "The dictionary is empty."
    
    if total_pairs <= 2:
        return False, "Since the dictionary contains 2 or less potential acronyms, the acronym list will be treated as invalid."
    

    invalid_details = "; ".join([f"{k}: {v}" for k, v in invalid_entries])

    invalid_percentage = 0.65
    invalid_check = len(invalid_entries) / total_pairs
    valid_pairs = len(acronym_dict) - len(check_invalid_entries)
    valid_percentage = valid_pairs / total_pairs
   
    if (valid_percentage >= threshold) and (invalid_check <=invalid_percentage):
        return True, "The acronym list has been extracted correctly."
    else:
        return False, (
            f"The acronym list did not meet the {threshold * 100}% validity threshold. "
            f"Validity: {valid_percentage * 100:.2f}%. "
            f"Invalid entries: {invalid_details}"
        )
    
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

def replace_acronyms(elements, logger: logging.Logger):
    """
    Replace acronyms in page_content of elements with their definitions, store used acronyms in metadata.
    If an acronym is defined (definition (acronym)), remove the acronym and parentheses.

    :param elements: List of elements containing metadata and content.
    :param logger: Logger for logging information and errors.
    :return: List of elements with acronyms replaced in page_content.
    """
    acronym_dicts = {}
    elements_to_process = []

    # Separate elements with acronym dictionaries and elements to process
    for element in elements:
        acronym_dict = element.metadata.get('acronym_list')
        if acronym_dict:
            acronym_dicts.update(acronym_dict)
        else:
            elements_to_process.append(element)

    if not acronym_dicts:
        logger.debug(f"'acronym_list' is empty for document '{element.metadata['filename']}'.")
        return


    # Compile the regex patterns once using all acronym keys and values
    ## NEED TO REFINE THIS REGEX PATTERN TO NOT REPLACE ACRONYMS NEXT TO HYPHENS '-' such as SEP-02-1
    pattern_acronym = re.compile(r'\b(' + '|'.join(map(re.escape, acronym_dicts.keys())) + r')\b')
    pattern_definition = re.compile(r'\b(' + '|'.join(map(lambda x: re.escape(x.replace(' and ', ' & ')), acronym_dicts.values())) + r')\s*\(\b([^)\s]+)\b\)')


    for element in elements_to_process:
        key_terms = []

        def replace_definition(match):
            definition = match.group(1)
            acronym = match.group(2)
            if acronym in acronym_dicts and acronym_dicts[acronym].replace(' and ', ' & ') == definition.replace(' and ', ' & '):
                key_terms.append(definition)
                logger.debug(f"Definition '{definition}' matched with acronym '{acronym}'.")
                return definition
            return match.group(0)

        def replace_acronym(match):
            acronym = match.group(0)
            replacement = acronym_dicts[acronym]
            key_terms.append(replacement)
            logger.debug(f"Acronym '{acronym}' replaced with '{replacement}'.")
            return replacement

        try:
            # First, replace definitions with acronyms
            element.page_content = pattern_definition.sub(replace_definition, element.page_content)
            # Then, replace standalone acronyms
            element.page_content = pattern_acronym.sub(replace_acronym, element.page_content)
            element.metadata['key_terms'] = list(set(key_terms))  # Store unique key terms
            logger.info(f"Acronyms replaced in element {id(element)} in {element.metadata['filename']}")
        except Exception as e:
            logger.error(f"Error replacing acronyms in element {id(element)} in {element.metadata['filename']}: {e}")

    return elements_to_process

def process_text_as_html_element(element: Any, logger: logging.Logger) -> Dict[str, Any]:
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
            acronym_dict = process_acronym_table(html_content)
            is_valid, validation_message = test_acronym_extraction(acronym_dict)

            if is_valid:
                element.metadata['acronym_list'] = acronym_dict
                element.metadata['text_as_html'] = None

                logger.info(f"Valid acronym list found for element {id(element)} in {element.metadata['filename']}")
            else:
                logger.info(f"No valid acronym list found for {id(element)} in {element.metadata['filename']}")
                
        elif not page_content.strip():
            logger.warning(f"page_content is empty and html contains no visible text in text_as_html metadata for element {id(element)} in {element.metadata['filename']}")
            # log_and_delete_element(element, logger)
            
    elif not page_content.strip():
        logger.warning(f"page_content is empty and no text_as_html metadata for element {id(element)} in {element.metadata['filename']} - Deleting element")
        # log_and_delete_element(element, logger)

    return element.metadata

def process_acronym_text_as_html(
        elements: List[Any], 
        logger: logging.Logger = None
        ) -> Tuple[List[Any], List[Dict[str, Any]]]:
    
    logger = logger if logger else logging.getLogger(__name__)
    
    html_processing_output = []

    logger.info(f"Starting process_acronym_text_as_html for {elements[0].metadata['filename']} with {len(elements)} elements")

    try:
        for element in elements:
        
            processed_metadata = process_text_as_html_element(element, logger)
            html_processing_output.append(processed_metadata)

    except Exception as e:
        logger.error(f"Error processing acronym as HTML for element {id(element)} in {element.metadata['filename']}: {e}")

    try:
        replace_acronyms(elements, logger)

    except Exception as e:
        logger.error(f"Error processing replacing acronyms with acronym_list for element {id(element)} in {element.metadata['filename']}: {e}")

    logger.info(f"Finished process_acronym_text_as_html for {element.metadata['filename']}")
    
    return elements, html_processing_output
