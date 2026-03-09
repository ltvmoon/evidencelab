"""
LangGraph research assistant using deepagents.

Uses LangChain's deepagents create_agent for a focused research loop:
  - Custom search tool for Qdrant document database
  - Autonomous multi-round search and synthesis
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from deepagents.graph import create_agent
from jinja2 import Environment, FileSystemLoader
from langchain_core.tools import tool

from ui.backend.services.search import search_chunks

logger = logging.getLogger(__name__)

# Jinja2 environment for prompt templates
PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"
_jinja_env = Environment(loader=FileSystemLoader(str(PROMPTS_DIR)), autoescape=True)


def _format_search_result(r: Any) -> Dict[str, Any]:
    """Format a Qdrant ScoredPoint into a plain dict."""
    payload = r.payload if hasattr(r, "payload") else r
    # Qdrant payloads use "map_title"; fall back to "title" for tests/dicts
    title = payload.get("map_title") or payload.get("title") or "Untitled"
    return {
        "chunk_id": getattr(r, "id", payload.get("chunk_id", "")),
        "doc_id": payload.get("doc_id", ""),
        "title": title,
        "text": payload.get("text", ""),
        "score": getattr(r, "score", payload.get("score", 0.0)),
        "page": payload.get("page_num", None),
        "headings": payload.get("headings", []),
    }


class SearchTracker:
    """Track search calls and accumulate results for source extraction."""

    def __init__(self, data_source: Optional[str] = None):
        self.data_source = data_source
        self.per_query: List[Dict[str, Any]] = []
        self.all_results: List[Dict[str, Any]] = []
        self._seen_ids: set = set()
        self._emitted_query_count: int = 0

    def search(self, query: str) -> List[Dict[str, Any]]:
        """Execute search, track results, return formatted dicts."""
        try:
            raw = search_chunks(
                query=query,
                limit=20,
                data_source=self.data_source,
                rerank=True,
            )
            formatted = [_format_search_result(r) for r in raw]
        except Exception as exc:
            logger.error("Search failed for query %r: %s", query, exc)
            formatted = []

        self.per_query.append({"query": query, "result_count": len(formatted)})

        for r in formatted:
            cid = r.get("chunk_id", "")
            if cid not in self._seen_ids:
                self.all_results.append(r)
                self._seen_ids.add(cid)

        return formatted

    def get_new_queries(self) -> List[Dict[str, Any]]:
        """Return only queries not yet emitted, advancing the cursor."""
        new = self.per_query[self._emitted_query_count :]
        self._emitted_query_count = len(self.per_query)
        return new

    def get_sources(self) -> List[Dict[str, Any]]:
        """Build deduplicated source references from accumulated results."""
        sources: List[Dict[str, Any]] = []
        seen_doc_ids: set = set()
        sorted_results = sorted(
            self.all_results,
            key=lambda x: x.get("score", 0),
            reverse=True,
        )
        for r in sorted_results:
            doc_id = r.get("doc_id", "")
            if doc_id and doc_id not in seen_doc_ids:
                text = r.get("text", "")
                sources.append(
                    {
                        "chunkId": r.get("chunk_id", ""),
                        "docId": doc_id,
                        "title": r.get("title", ""),
                        "text": (text[:200] + "...") if len(text) > 200 else text,
                        "score": r.get("score", 0.0),
                        "page": r.get("page"),
                    }
                )
                seen_doc_ids.add(doc_id)
        return sources


def _build_search_tool(tracker: SearchTracker):
    """Create a search tool that uses the given tracker."""

    @tool
    def search_documents(query: str) -> str:
        """Search the document database for information relevant to the query.

        Use this tool to find evidence, facts, and insights from indexed
        documents. Each result includes a document title, text excerpt, and
        relevance score. Call this tool multiple times with different queries
        to gather comprehensive evidence before writing your response.

        Args:
            query: The search query — be specific and focused for best results.
        """
        results = tracker.search(query)

        if not results:
            return "No results found for this query."

        lines = []
        for i, r in enumerate(results, 1):
            doc_id = r.get("doc_id", "")
            title = r.get("title", "Untitled")
            text = r.get("text", "")
            lines.append(f"[{i}] Document: {title} (doc_id: {doc_id})\n{text}\n---")

        return f"Found {len(results)} results:\n\n" + "\n".join(lines)

    return search_documents


def _load_system_prompt(data_source: Optional[str] = None) -> str:
    """Load and render the assistant system prompt."""
    template = _jinja_env.get_template("assistant_system.j2")
    return template.render(data_source=data_source)


def build_research_agent(
    llm,
    data_source: Optional[str] = None,
) -> tuple:
    """
    Build a deep research agent.

    Args:
        llm: LangChain chat model instance
        data_source: Optional data source to restrict search

    Returns:
        Tuple of (compiled_agent, search_tracker)
    """
    tracker = SearchTracker(data_source=data_source)
    search_tool = _build_search_tool(tracker)
    system_prompt = _load_system_prompt(data_source)

    agent = create_agent(
        model=llm,
        tools=[search_tool],
        system_prompt=system_prompt,
    )

    logger.info("Built research agent for data_source=%s", data_source)
    return agent, tracker
