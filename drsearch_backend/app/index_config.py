# index_config.py

from . import System_Prompts

# Configuration dictionary for index names, attributes, and response templates
INDEX_CONFIG = {
    "SEPs_F_T_C_W_A_V": {
        "attributes": ["file_path", "filename", "url", "text_as_html"],
        "index_key": "page_content",
        "response_template": System_Prompts.RESPONSE_TEMPLATE_SEPS,
        "DECOMPOSER": System_Prompts.QUESTION_DECOMPOSER2,
        "PN_TO_FILE_MAPPING": None,
    },
    "SEPs_F_T_C_W_A_V_Summaries": {
        "attributes": ["file_path", "filename", "url", "text_as_html"],
        "index_key": "page_content",
        "response_template": System_Prompts.RESPONSE_TEMPLATE_SEPS,
        "DECOMPOSER": System_Prompts.QUESTION_DECOMPOSER2,
        "PN_TO_FILE_MAPPING": None,
    },
    "SEPs_F_T_C_W_A_V_Summaries_5000": {
        "attributes": ["file_path", "filename", "url", "text_as_html"],
        "index_key": "page_content",
        "response_template": System_Prompts.RESPONSE_TEMPLATE_SEPS,
        "DECOMPOSER": System_Prompts.QUESTION_DECOMPOSER2,
        "PN_TO_FILE_MAPPING": None,
    },
    "LangChain_agent_docs": {
        "attributes": ["source", "title"],
        "index_key": "text",
        "response_template": System_Prompts.RESPONSE_TEMPLATE_LANGCHAIN,
        "DECOMPOSER": System_Prompts.QUESTION_DECOMPOSER2,
        "PN_TO_FILE_MAPPING": None,
    },
    "AZURE_10000MaxChunk": {
        "attributes": ["file_directory", "filename"],
        "index_key": "page_content",
        "response_template": System_Prompts.RESPONSE_TEMPLATE_AZURE,
        "DECOMPOSER": System_Prompts.QUESTION_DECOMPOSER2,
        "PN_TO_FILE_MAPPING": None,
    },
    "WEAVIATE_DOCS": {
        "attributes": ["file_directory", "filename"],
        "index_key": "page_content",
        "response_template": System_Prompts.RESPONSE_TEMPLATE_WEAVIATE,
        "DECOMPOSER": System_Prompts.QUESTION_DECOMPOSER2,
        "PN_TO_FILE_MAPPING": None,
    },
    "JACSKE_HDD_GPT": {
        "attributes": ["file_directory", "filename"],
        "index_key": "page_content",
        "response_template": System_Prompts.RESPONSE_TEMPLATE_JAC_SKE,
        "DECOMPOSER": System_Prompts.QUESTION_DECOMPOSER2,
        "PN_TO_FILE_MAPPING": None,
    },
    "JACSKE_Program": {
        "attributes": ["file_path", "filename", "url", "text_as_html"],
        "index_key": "page_content",
        "response_template": System_Prompts.RESPONSE_TEMPLATE_JAC_SKE_PROGRAM_FOR_TECHS,
        "DECOMPOSER": System_Prompts.QUESTION_DECOMPOSER_JACSKE,
        "PN_TO_FILE_MAPPING": "JACSKE_PROD_DEPLOY.csv",
    },
    "test20240712": {
        "attributes": ["file_path", "filename", "url", "text_as_html"],
        "index_key": "page_content",
        "response_template": System_Prompts.RESPONSE_TEMPLATE_JAC_SKE_PROGRAM,
        "DECOMPOSER": System_Prompts.QUESTION_DECOMPOSER2,
        "PN_TO_FILE_MAPPING": None,
    },
    "Injected_URL3": {
        "attributes": ["file_path", "url"],
        "index_key": "page_content",
        "response_template": System_Prompts.RESPONSE_TEMPLATE_SEPS,
        "DECOMPOSER": System_Prompts.QUESTION_DECOMPOSER2,
        "PN_TO_FILE_MAPPING": None,
    },
    "HFSS_GUIDE_20240813": {
        "attributes": ["file_path", "filename", "url", "text_as_html"],
        "index_key": "page_content",
        "response_template": System_Prompts.RESPONSE_TEMPLATE_HFSS,
        "DECOMPOSER": System_Prompts.QUESTION_DECOMPOSER_HFSS,
        "PN_TO_FILE_MAPPING": None,
    },
    "Adacstest20250205": {
        "attributes": ["file_path", "filename", "url", "text_as_html"],
        "index_key": "page_content",
        "response_template": System_Prompts.RESPONSE_TEMPLATE_ADACS_TECH,
        "DECOMPOSER": System_Prompts.QUESTION_DECOMPOSER_ADACS_TECH,
        "PN_TO_FILE_MAPPING": "ADACS_TECH.csv",
    },
}
