## Pipeline Configuration

The document processing pipeline is modular and managed by `orchestrator.py`. Configure it to process your documents through parsing, chunking, summarization, tagging, and indexing.

### Data Source Configuration

Edit [`config.json`](https://github.com/dividor/evidencelab/blob/main/config.json) in the repo root to define your data sources:

* `datasources` — define each data source with its `data_subdir`, `field_mapping`, and processing options
* `field_mapping` — map your metadata JSON fields to Evidence Lab's internal fields (title, organization, year, etc.)
* The UI reads the same `config.json` via Docker Compose

### Pipeline Stages

1. **Parser** (`parser.py`) — uses [Docling](https://github.com/DS4SD/docling) for PDF/Word parsing with hierarchical structure detection, image/table extraction, and footnote identification
2. **Chunker** (`chunker.py`) — splits parsed text into searchable chunks respecting semantic boundaries, with footnote resolution and image association
3. **Summarizer** (`summarizer.py`) — generates document summaries using a Map-Reduce LLM approach
4. **Tagger** (`tagger.py`) — classifies chunks into taxonomy categories (findings, methodology, executive_summary, etc.) and supports configurable document-level taxonomies (e.g., SDGs)
5. **Indexer** (`indexer.py`) — stores content in Qdrant with multi-vector indexing (dense + sparse)

### Running the Pipeline

```bash
# Via Docker
docker compose exec pipeline \
  python -m pipeline.orchestrator --data-source <source> --skip-download --num-records 10

# On host (for hardware acceleration)
./scripts/pipeline/run_pipeline_host.sh
```

### AI Models

The pipeline uses AI models for:

* Vector embeddings (multilingual-e5-large, Azure text-embedding-3)
* LLM document summarization
* LLM tagging
* LLM document structure analysis

Models are configurable via `config.json` and environment variables. Both open-source (Huggingface) and proprietary (Azure Foundry) models are supported.

### Optimization

* **Hardware acceleration** — parsing can leverage GPUs and MPS acceleration when run on the host
* **Qdrant performance** — for best IO performance, Qdrant can be run on the host with int8 quantized vectors in-memory
