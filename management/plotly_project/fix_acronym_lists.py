import os
from langchain.chains import LLMChain
from langchain.prompts import ChatPromptTemplate
from langchain.schema import BaseOutputParser
from openai import AzureOpenAI
import json
from Update_Weaviate import get_weaviate_ids_from_field_values, weaviate_client

api_version = "2024-02-01"
model_4 = "gpt-4"
deployment_name = model_4
embedder_model = "text-embedding-ada-002"
NUMBER_OF_DOCS_RETRIEVED = 1
MAX_RETRIES = 3

WEAVIATE_URL = os.environ.get("WEAVIATE_URL")
WEAVIATE_API_KEY = os.environ.get("WEAVIATE_API_KEY")
WEAVIATE_DOCS_INDEX_NAME = 'SEPs_F_T_C_W_A_V' 

llm = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"), 
    api_key=os.getenv(""), 
    api_version=api_version,
)


# Define the prompt
system_prompt = """
Given the following text, determine if it is an acronym list. If it is, respond with a dictionary format:
{
    "acronyms": {
        "acronym1": "Acronym Definition",
        "acronym2": "Acronym Definition",
        "acronym3": "Acronym Definition"
    }
}
If it is not an acronym list, respond with:
{
    "acronyms": None
}
"""

def get_acronym_list(text):
    response = llm.chat.completions.create(
        model = "gpt-4",
        messages=[
            {"role": "system", "content": system_prompt},
            # {"role": "user", "content": html_1shota},
            # {"role": "assistant", "content": html_1shotb},
            {"role": "user", "content": text},
        ]
    )
    response0 = json.loads(response.choices[0].message.content.strip())
    return response0


with weaviate_client(WEAVIATE_URL, WEAVIATE_API_KEY) as client:

    ids = []
    for element in elements:
        acronym_list = get_acronym_list(element.page_content)
        if acronym_list:
            file_path = element.metadata.file_path
            ids = get_weaviate_ids_from_field_values(client,WEAVIATE_DOCS_INDEX_NAME, 'file_path', file_path)
    print(ids)
# # Example usage
# def process_text(text: str) -> dict:
#     return get_acronym_list(text)

# # Example input text
# text = """
# The recent advancements in technology have brought significant changes in various fields. A notable example is the rise of AI: Artificial Intelligence, which is revolutionizing industries. Moreover, companies are heavily investing in ML: Machine Learning, transforming data analytics. The field of NLP: Natural Language Processing is also gaining traction, enabling better human-computer interactions. However, there have been reports that...

# ...the integration of AI: Artificial Intelligence and ML: Machine Learning presents unique challenges. For instance, in some applications, the accuracy of ML: Machine Learning models can be affected by data quality. Similarly, implementing NLP: Natural Langage Processing in real-time systems has its own set of difficulties.

# In addition, there is a growing concern about the ethical implications of AI: Artificial Intelligenc and its impact on privacy. Researchers are focusing on making ML: Machine Learnin more transparent and fair. This ongoing debate highlights the need for responsible development of these technologies.

# Furthermore, combining AI: Artificial Intelligence, ML: Machine Learning, and NLP: Natural Language Processin can lead to innovative solutions. Yet, the scalability of these technologies remains a critical issue. Efforts are being made to overcome these barriers and enhance the efficiency of AI: Artifical Intelligence systems.

# In conclusion, while AI: Artificial Intelligence, ML: Machine Learning, and NLP: Natural Language Processing hold great promise, it is crucial to address the associated challenges. Continued research and ethical considerations will play a vital role in the sustainable development of these fields.
# """

# # Process the text
# result = process_text(text)
# print(result)
