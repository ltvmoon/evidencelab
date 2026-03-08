## Getting Started

For more detailed instructions refer to the [Evidence Lab GitHub Repo](https://github.com/dividor/evidencelab).

1. **Configure data sources**
   - Edit [`config.json`](https://github.com/dividor/evidencelab/blob/main/config.json) in the repo root to define `datasources`, `data_subdir`, and `field_mapping`, along with fields to control how your documents are parsed.
   - The UI reads the same `config.json` via Docker Compose.

2. **Set environment variables**
   - Copy [`.env.example`](https://github.com/dividor/evidencelab/blob/main/.env.example) to `.env`.
   - Fill in the API keys and service URLs required by the pipeline and UI.

3. **Add documents + metadata**
   - Save documents under `data/<data_subdir>/pdfs/<organization>/<year>/`.
   - For each document, include a JSON metadata file with the same base name.
   - If a download failed, add a `.error` file with the same base name (scanner records these).

   Example layout:
   ```
   data/
     uneg/
       pdfs/
         UNDP/
           2024/
             report_123.pdf
             report_123.json
             report_124.error (optional, if download failed)
   ```

4. **Run the pipeline (Docker)**
   ```bash
   # Start services
   docker compose up -d --build

   # Run the orchestrator (example: UNEG)
   docker compose exec pipeline \
     python -m pipeline.orchestrator --data-source uneg --skip-download --num-records 10
   ```

5. **Access the Evidence Lab UI**
   - Open http://localhost:3000
   - Select your data source and search the indexed documents

For more detailed information see the [Evidence Lab GitHub Repo](https://github.com/dividor/evidencelab).
