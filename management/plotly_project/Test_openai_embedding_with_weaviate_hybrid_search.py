import os
from langchain_openai import AzureOpenAIEmbeddings 
import weaviate
import weaviate.classes as wvc
from weaviate.classes.init import Auth
from weaviate.classes.query import HybridFusion
import pprint


os.environ['AZURE_OPENAI_API_KEY'] = 'secret'
os.environ["AZURE_OPENAI_ENDPOINT"] = 'secret'
WEAVIATE_URL = os.environ.get("WEAVIATE_URL")
WEAVIATE_API_KEY = os.environ.get("WEAVIATE_API_KEY")
WEAVIATE_DOCS_INDEX_NAME = 'JACSKE_Program'

api_version="2024-02-01"
model4="gpt-4"
model35="gpt-35-turbo"
embedder_model = "text-embedding-ada-002"

embeddings_client = AzureOpenAIEmbeddings(
    model=embedder_model, 
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"), 
    api_key=os.getenv("AZURE_OPENAI_API_KEY"), 
    chunk_size=200, 
    api_version=api_version,
)

text = "Where is the XMIT Trig signal created"


def search_weaviate(index, query, alpha, limit = 5, query_properties= None, return_score=False, explain_score=False, fusion_type='RELATIVE_SCORE'):

    weaviate_client = client.collections.get(index)

    embedding = embeddings_client.embed_query(text)

    if fusion_type == 'RELATIVE_SCORE':
        fusion_type=HybridFusion.RELATIVE_SCORE
    elif fusion_type == 'RANKED' or fusion_type == None:
        fusion_type=HybridFusion.RANKED
    else:
        print(f"{fusion_type} is not a valid fusion setting")


    result = weaviate_client.query.hybrid(
        query=text,
        vector=embedding,
        alpha=alpha,
        return_metadata=wvc.query.MetadataQuery(score=return_score, explain_score=explain_score),
        query_properties=query_properties,#array of strings to limit the set of properties for the BM25 component of the search. If unspecified, all text properties will be searched.
        #Specific properties can be boosted by a factor specified as a number after the caret sign, for example properties: ["title^3", "summary"].
        # filters=wvc.query.Filter.by_property("wordCount").less_than(1000),
        fusion_type=fusion_type,
        # return_properties=["references"],
        limit=limit,
    )
    return result.objects




with weaviate.connect_to_local(auth_credentials=Auth.api_key(WEAVIATE_API_KEY)) as client:

    print(client.is_ready())
    weaviate_client = client.collections.get(WEAVIATE_DOCS_INDEX_NAME)

    embedding = embeddings_client.embed_query(text)

    result = search_weaviate(
        WEAVIATE_DOCS_INDEX_NAME,
        text,
        alpha = .75, 
        limit = 30, 
        query_properties= None, 
        return_score=True, 
        explain_score=False, 
        fusion_type='RELATIVE_SCORE'
    )

 
    for o in result:
        pprint.pprint(o.properties['page_content'])
        print(o.metadata.score)
        print(o.metadata.explain_score)
        print("*********************")
