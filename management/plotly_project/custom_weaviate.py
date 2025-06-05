"""
CustomWeaviate Class

Purpose:
This custom wrapper class, CustomWeaviate, was created to extend the functionality 
of the existing Weaviate class from the langchain_community library. The primary 
purpose of this wrapper is to include additional properties, specifically 'vector' 
and 'id', in the results returned by the max_marginal_relevance_search method. This 
extension ensures that these properties are consistently available in the search 
results, providing more detailed information for downstream processing and analysis.

Description:
The CustomWeaviate class inherits from the base Weaviate class and overrides the 
max_marginal_relevance_search and max_marginal_relevance_search_by_vector methods. 
The overridden methods ensure that additional properties like 'vector' and 'id' are 
included in the search results when specified. The implementation includes checks to 
handle cases where these additional properties are not requested, thereby preventing 
KeyErrors and ensuring robust functionality.

Key Features:
- Extends max_marginal_relevance_search to include 'vector' and 'id' in results.
- Includes error handling to manage cases where additional properties are not present.
- Provides detailed metadata for each document returned in the search results.

Library Versions:
- langchain-community: 0.2.4
- weaviate-client: 4.6.5

This custom wrapper is essential for applications requiring enriched metadata in search 
results, particularly in scenarios involving document similarity and relevance ranking.
"""



from langchain_community.vectorstores import Weaviate
from langchain_community.vectorstores.utils import maximal_marginal_relevance

from langchain.schema import Document
from typing import List, Any
import numpy as np

class CustomWeaviate(Weaviate):
    def max_marginal_relevance_search(
        self,
        query: str,
        k: int = 4,
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
        **kwargs: Any,
    ) -> List[Document]:
        if self._embedding is not None:
            embedding = self._embedding.embed_query(query)
        else:
            raise ValueError("max_marginal_relevance_search requires a suitable Embeddings object")

        return self.max_marginal_relevance_search_by_vector(
            embedding, k=k, fetch_k=fetch_k, lambda_mult=lambda_mult, **kwargs
        )

    def max_marginal_relevance_search_by_vector(
        self,
        embedding: List[float],
        k: int = 4,
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
        additional: List[str] = None,
        **kwargs: Any,
    ) -> List[Document]:
        vector = {"vector": embedding}
        query_obj = self._client.query.get(self._index_name, self._query_attrs)
        if kwargs.get("where_filter"):
            query_obj = query_obj.with_where(kwargs.get("where_filter"))
        if kwargs.get("tenant"):
            query_obj = query_obj.with_tenant(kwargs.get("tenant"))

        if additional is None:
            additional = []

        results = (
            query_obj.with_additional(additional)
            .with_near_vector(vector)
            .with_limit(fetch_k)
            .do()
        )

        payload = results["data"]["Get"][self._index_name]

        if 'vector' in additional:
            embeddings = [result["_additional"]["vector"] for result in payload]
            mmr_selected = maximal_marginal_relevance(
                np.array(embedding), embeddings, k=k, lambda_mult=lambda_mult
            )
        else:
            mmr_selected = range(min(len(payload), k))

        docs_and_scores = []
        for idx in mmr_selected:
            text = payload[idx].pop(self._text_key)
            meta = payload[idx]
            score = None
            if 'vector' in additional:
                vector = payload[idx]["_additional"]["vector"]
                meta["vector"] = vector
            if 'id' in additional:
                doc_id = payload[idx]["_additional"]["id"]
                meta["id"] = doc_id
            if 'score' in additional:
                score = np.dot(vector, embedding)  # Calculate the score
                meta["score"] = score  # Add the score to metadata
            payload[idx].pop("_additional", None)
            docs_and_scores.append(Document(page_content=text, metadata=meta))
        return docs_and_scores
