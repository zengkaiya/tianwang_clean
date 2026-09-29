#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tqdm import tqdm


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Filter JSONL rows by caption similarity threshold.")
    parser.add_argument(
        "--input",
        default="outputs/final/pairs/2015/image_text_pairs_new_with_caption_similarity_sorted.jsonl",
    )
    parser.add_argument("--threshold", type=float, required=True)
    parser.add_argument("--output", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"input not found: {input_path}")

    output_path = (
        Path(args.output)
        if args.output
        else input_path.with_name(f"{input_path.stem}_ge_{args.threshold:g}.jsonl")
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    selected = 0
    invalid = 0
    with input_path.open("r", encoding="utf-8") as input_file, output_path.open("w", encoding="utf-8") as output_file:
        for line in tqdm(input_file, desc="Filtering pairs", unit="row", dynamic_ncols=True):
            s = line.strip()
            if not s:
                continue
            total += 1
            try:
                row: Any = json.loads(s)
            except Exception:
                invalid += 1
                continue
            if not isinstance(row, dict):
                invalid += 1
                continue

            try:
                similarity = float(row.get("caption_similarity"))
            except (TypeError, ValueError):
                invalid += 1
                continue

            if similarity >= args.threshold:
                output_file.write(json.dumps(row, ensure_ascii=False) + "\n")
                selected += 1

    print(f"Total rows: {total}")
    print(f"Selected rows: {selected}")
    print(f"Invalid rows: {invalid}")
    print(f"Output: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
