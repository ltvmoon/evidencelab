## Search

Evidence Lab search is powered by hybrid retrieval and AI.

### Hybrid Search

Uses **Reciprocal Rank Fusion (RRF)** to mathematically combine results from Semantic Search (Dense vectors) and Keyword Search (Sparse/BM25 vectors). This captures both "conceptual matches" and "exact phrase matches".

### Reranking

Optionally applies a reranking step to re-score the top results, significantly improving precision. Supports Cohere Rerank (via Azure Foundry) and Jina Reranker (via Huggingface).

### Boosting

* **Recency Boosting**: Applies a Gaussian decay function to boost newer documents while retaining relevance for older, highly distinct matches.
* **Field Boosting**: Configurable per data source, detects field values (e.g., country names, organizations) mentioned in the query and boosts matching results. At weight < 1.0, uses a multiplicative bonus (`score * (1 + weight)`) so non-matching results are never penalized. At weight = 1.0, acts as a hard filter — results whose metadata field does not match the detected value are excluded entirely.

### Faceted Navigation

Filter results by Organization, Year, Language, and Format using the facet panel.

### Cross-Lingual Features

* **Translation**: Translate search results (titles + snippets) into 10+ languages on request.
* **Semantic Highlighting**: Highlights relevant phrases in the result snippet effectively, even when the search terms are in a different language from the result.

### AI Search Summary

Generates a direct answer to the user's query by synthesizing the top search results.

### Preview & Deep-Linking

Integrated PDF viewer that opens directly to the specific page and highlights the relevant paragraph.
