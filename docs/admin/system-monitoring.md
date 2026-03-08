## System Monitoring

Evidence Lab includes built-in tools for monitoring the pipeline and data quality.

### Documents Dashboard

Visual breakdown of the corpus by Agency, Year, Type, and Language. Provides a quick overview of what has been indexed and highlights any imbalances in coverage.

### Data Grid

Filterable table of all documents with:

* Status tracking — `Indexed`, `Error`, `Parsed`
* Direct Web/PDF links
* Sortable columns for quick inspection

### Inspection Tools

* **Chunk Inspector** — view the raw JSON, text, and vector content of any document chunk to debug indexing issues
* **TOC Editor** — inspect and adjust the inferred section classifications from the Table of Contents

### Pipeline Controls

Manually re-trigger the processing pipeline for specific documents directly from the UI. Useful for reprocessing documents after configuration changes or fixing errors.

### Error Traceability

Full visibility into processing errors, including raw error logs and stack traces preserved in the database. Each document's processing history is tracked so you can quickly identify and resolve issues.
