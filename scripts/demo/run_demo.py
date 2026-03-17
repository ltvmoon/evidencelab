#!/usr/bin/env python3
"""
run_demo.py - One-command demo that downloads a few documents and runs the
full Evidence Lab pipeline, so users can test quickly.

Usage:
    # Docker must be running (docker compose up -d --build)
    python scripts/demo/run_demo.py

    # Customise the number of documents (default: 3)
    python scripts/demo/run_demo.py --num-docs 5

What it does:
    1. Adds a "Demo" datasource entry to config.json (cloned from World Bank
       config but pointing at data/demo and the demo downloader).
    2. Downloads documents from the World Bank API via scripts/demo/download.py.
    3. Runs the full pipeline inside the Docker pipeline container.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config.json"
DOWNLOAD_SCRIPT = PROJECT_ROOT / "scripts" / "demo" / "download.py"

DEMO_DATASOURCE_KEY = "Demo"
DEMO_DATA_SUBDIR = "demo"


def load_config():
    """Load the project config.json."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config):
    """Write config.json back to disk."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        f.write("\n")


def ensure_demo_datasource(config):
    """Add the Demo datasource to config.json if it doesn't already exist.

    Clones the World Bank datasource config and adjusts the data_subdir,
    download command, and display settings for demo use.
    """
    datasources = config.get("datasources", {})

    if DEMO_DATASOURCE_KEY in datasources:
        print(f"  '{DEMO_DATASOURCE_KEY}' datasource already exists in config.json")
        return False

    # Find World Bank config to clone
    wb_key = None
    for key in datasources:
        if datasources[key].get("data_subdir") == "worldbank":
            wb_key = key
            break

    if wb_key is None:
        print("ERROR: Could not find a World Bank datasource in config.json to clone.")
        print(
            "       Please ensure config.json has a datasource with data_subdir='worldbank'."
        )
        sys.exit(1)

    # Deep-copy the World Bank config
    import copy

    demo_config = copy.deepcopy(datasources[wb_key])

    # Override for demo
    demo_config["data_subdir"] = DEMO_DATA_SUBDIR
    demo_config["example_queries"] = [
        "What types of fraud are most commonly reported?",
        "How does the World Bank investigate allegations of corruption?",
    ]

    # Point download at the demo downloader
    demo_config["pipeline"]["download"] = {
        "command": "scripts/demo/download.py",
        "args": [
            "--data-dir",
            "{data_dir}",
            "--limit",
            "{num_records}",
        ],
    }

    datasources[DEMO_DATASOURCE_KEY] = demo_config
    config["datasources"] = datasources
    print(f"  Added '{DEMO_DATASOURCE_KEY}' datasource to config.json")
    return True


def download_documents(num_docs):
    """Run the demo downloader to fetch documents."""
    data_dir = PROJECT_ROOT / "data" / DEMO_DATA_SUBDIR
    cmd = [
        sys.executable,
        str(DOWNLOAD_SCRIPT),
        "--limit",
        str(num_docs),
        "--data-dir",
        str(data_dir),
    ]
    print(f"  Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        print("ERROR: Download failed.")
        sys.exit(1)


def run_pipeline(num_docs):
    """Run the full pipeline inside the Docker pipeline container."""
    cmd = [
        "docker",
        "compose",
        "exec",
        "pipeline",
        "python",
        "-m",
        "pipeline.orchestrator",
        "--data-source",
        DEMO_DATASOURCE_KEY,
        "--num-records",
        str(num_docs),
        "--skip-download",
    ]
    print(f"  Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        print("ERROR: Pipeline failed. Are Docker services running?")
        print("       Try: docker compose up -d --build")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Run the Evidence Lab demo: download documents "
            "and process them through the pipeline."
        )
    )
    parser.add_argument(
        "--num-docs",
        type=int,
        default=3,
        help="Number of documents to download and process (default: 3)",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip downloading documents (use previously downloaded files)",
    )
    parser.add_argument(
        "--skip-pipeline",
        action="store_true",
        help="Skip running the pipeline (only download documents and add config)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  Evidence Lab Demo")
    print("=" * 60)
    print()

    # Step 1: Ensure demo datasource in config.json
    print("[1/3] Configuring demo datasource...")
    config = load_config()
    changed = ensure_demo_datasource(config)
    if changed:
        save_config(config)
    print()

    # Step 2: Download documents
    if args.skip_download:
        print("[2/3] Skipping download (--skip-download)")
    else:
        print(f"[2/3] Downloading {args.num_docs} documents from World Bank API...")
        download_documents(args.num_docs)
    print()

    # Step 3: Run pipeline
    if args.skip_pipeline:
        print("[3/3] Skipping pipeline (--skip-pipeline)")
    else:
        print(f"[3/3] Running pipeline on {args.num_docs} documents...")
        print(
            "       (Ensure Docker services are running: docker compose up -d --build)"
        )
        run_pipeline(args.num_docs)
    print()

    print("=" * 60)
    print("  Demo complete!")
    print()
    print("  Open http://localhost:3000 to explore the results.")
    print(f"  Select the '{DEMO_DATASOURCE_KEY}' data source in the UI.")
    print("=" * 60)


if __name__ == "__main__":
    main()
