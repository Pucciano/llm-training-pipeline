#!/usr/bin/env python3
"""Download Hugging Face parquet dataset files into a local folder.

This script downloads parquet files from a Hugging Face dataset repository
and stores them under:

    datasets/parquet/{dataset_name}

Authentication is optional. For private datasets you can provide a token via
the ``--token`` argument or the ``HF_TOKEN`` environment variable.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Download parquet files from a Hugging Face dataset repository "
            "into datasets/parquet/{dataset_name}."
        )
    )
    parser.add_argument(
        "dataset_id",
        help="Hugging Face dataset id (for example: org_or_user/dataset_name).",
    )
    parser.add_argument(
        "--revision",
        default="main",
        help="Dataset revision to download (default: main).",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("datasets/parquet"),
        help="Root output directory (default: datasets/parquet).",
    )
    parser.add_argument(
        "--token",
        default=None,
        help=(
            "Optional Hugging Face token. If omitted, HF_TOKEN environment "
            "variable is used."
        ),
    )
    return parser.parse_args()


def _dataset_name(dataset_id: str) -> str:
    """Extract the dataset folder name from a dataset ID."""
    parts = [part for part in dataset_id.split("/") if part]
    if not parts:
        raise ValueError(f"Invalid dataset id: {dataset_id!r}")
    return parts[-1]


def _copy_parquet_files(snapshot_path: Path, destination: Path) -> int:
    """Copy parquet files from the snapshot path to the destination.

    Args:
        snapshot_path: Local snapshot path returned by Hugging Face Hub.
        destination: Destination directory for copied parquet files.

    Returns:
        Number of copied parquet files.
    """
    parquet_files = sorted(snapshot_path.rglob("*.parquet"))
    copied_count = 0

    for parquet_file in parquet_files:
        relative_path = parquet_file.relative_to(snapshot_path)
        target_file = destination / relative_path
        target_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(parquet_file, target_file)
        copied_count += 1

    return copied_count


def main() -> int:
    """Run the script entrypoint."""
    args = _parse_args()

    try:
        import huggingface_hub
        import huggingface_hub.utils
    except ModuleNotFoundError:
        print(
            "Missing dependency: huggingface_hub. Install it with: "
            "pip install huggingface-hub",
            file=sys.stderr,
        )
        return 1

    token = args.token or os.environ.get("HF_TOKEN")
    dataset_name = _dataset_name(args.dataset_id)
    destination = args.output_root / dataset_name
    destination.mkdir(parents=True, exist_ok=True)

    try:
        snapshot_location = huggingface_hub.snapshot_download(
            repo_id=args.dataset_id,
            repo_type="dataset",
            revision=args.revision,
            token=token,
            allow_patterns=["**/*.parquet", "*.parquet"],
        )
    except huggingface_hub.utils.HfHubHTTPError as error:
        print(
            "Failed to download dataset from Hugging Face Hub. "
            "If this is a private dataset, set HF_TOKEN or use --token.",
            file=sys.stderr,
        )
        print(f"Details: {error}", file=sys.stderr)
        return 1
    except Exception as error:  # pylint: disable=broad-exception-caught
        print(
            f"Unexpected error while downloading dataset: {error}",
            file=sys.stderr,
        )
        return 1

    copied_files = _copy_parquet_files(Path(snapshot_location), destination)
    if copied_files == 0:
        print(
            "Download completed, but no parquet files were found in the "
            "dataset repository.",
            file=sys.stderr,
        )
        return 1

    print(f"Dataset: {args.dataset_id}")
    print(f"Revision: {args.revision}")
    print(f"Destination: {destination}")
    print(f"Parquet files copied: {copied_files}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
