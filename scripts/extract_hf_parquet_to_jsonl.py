#!/usr/bin/env python3
"""Extract local Hugging Face parquet dataset files into JSONL files.

This script reads parquet files from:

    datasets/parquet/{dataset_name}

and writes JSONL files to:

    dataset/{fileformat}/{dataset_name}

By default, ``fileformat`` is ``jsonl``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Extract parquet files from datasets/parquet/{dataset_name} "
            "to dataset/{fileformat}/{dataset_name} as JSONL."
        )
    )
    parser.add_argument(
        "dataset_name",
        help="Dataset folder name under datasets/parquet/.",
    )
    parser.add_argument(
        "--input-root",
        type=Path,
        default=Path("datasets/parquet"),
        help="Root directory containing parquet datasets.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("dataset"),
        help="Root output directory (default: dataset).",
    )
    parser.add_argument(
        "--fileformat",
        default="jsonl",
        choices=["jsonl"],
        help="Output file format folder name (default: jsonl).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing JSONL files.",
    )
    return parser.parse_args()


def _write_records_jsonl(records: list[dict], output_path: Path) -> None:
    """Write dictionary records to a JSONL file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output_file:
        for record in records:
            output_file.write(json.dumps(record, ensure_ascii=False) + "\n")


def _extract_one_parquet(
    parquet_path: Path,
    source_root: Path,
    output_root: Path,
    overwrite: bool,
) -> tuple[Path, int]:
    """Extract one parquet file into one JSONL file.

    Args:
        parquet_path: Input parquet file path.
        source_root: Base root to keep relative structure.
        output_root: Root output path for JSONL files.
        overwrite: Whether existing files may be overwritten.

    Returns:
        Tuple with output JSONL path and row count.
    """
    try:
        import pandas as pd
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "Missing dependency 'pandas'. Install with: pip install pandas"
        ) from error

    relative_parquet = parquet_path.relative_to(source_root)
    output_path = output_root / relative_parquet.with_suffix(".jsonl")

    if output_path.exists() and not overwrite:
        raise FileExistsError(
            f"Output file already exists: {output_path}. "
            "Use --overwrite to replace it."
        )

    dataframe = pd.read_parquet(parquet_path)
    records = dataframe.to_dict(orient="records")
    _write_records_jsonl(records, output_path)
    return output_path, len(records)


def main() -> int:
    """Run parquet to JSONL extraction."""
    args = _parse_args()

    source_dir = args.input_root / args.dataset_name
    destination_dir = args.output_root / args.fileformat / args.dataset_name

    if not source_dir.exists() or not source_dir.is_dir():
        print(
            f"Input dataset directory not found: {source_dir}",
            file=sys.stderr,
        )
        return 1

    parquet_files = sorted(source_dir.rglob("*.parquet"))
    if not parquet_files:
        print(
            f"No parquet files found in: {source_dir}",
            file=sys.stderr,
        )
        return 1

    extracted_files = 0
    extracted_rows = 0
    for parquet_path in parquet_files:
        try:
            output_path, row_count = _extract_one_parquet(
                parquet_path=parquet_path,
                source_root=source_dir,
                output_root=destination_dir,
                overwrite=args.overwrite,
            )
        except Exception as error:  # pylint: disable=broad-exception-caught
            print(
                f"Failed to extract {parquet_path}: {error}",
                file=sys.stderr,
            )
            return 1

        extracted_files += 1
        extracted_rows += row_count
        print(f"Extracted: {parquet_path} -> {output_path} ({row_count} rows)")

    print("Extraction complete.")
    print(f"Dataset: {args.dataset_name}")
    print(f"Output directory: {destination_dir}")
    print(f"Parquet files processed: {extracted_files}")
    print(f"Rows exported: {extracted_rows}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
