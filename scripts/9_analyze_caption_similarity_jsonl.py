#!/usr/bin/env python3

from __future__ import annotations

import argparse
import heapq
import json
import multiprocessing as mp
import statistics
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from tqdm import tqdm


def iter_line_chunks(path: Path, chunk_size: int):
    chunk: list[str] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            chunk.append(line)
            if len(chunk) >= chunk_size:
                yield chunk
                chunk = []
    if chunk:
        yield chunk


def parse_similarity(row: dict[str, Any]) -> float | None:
    value = row.get("caption_similarity")
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return score if score == score else None


def sort_chunk(lines: list[str]) -> tuple[list[tuple[float, str]], list[str]]:
    valid: list[tuple[float, str]] = []
    invalid: list[str] = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        try:
            row = json.loads(s)
        except Exception:
            invalid.append(s + "\n")
            continue
        if not isinstance(row, dict):
            invalid.append(s + "\n")
            continue
        score = parse_similarity(row)
        if score is None:
            invalid.append(s + "\n")
            continue
        valid.append((score, s + "\n"))

    valid.sort(key=lambda item: item[0], reverse=True)
    return valid, invalid


def write_sorted_chunk(
    result: tuple[list[tuple[float, str]], list[str]], temp_dir: Path, chunk_id: int
) -> tuple[Path, Path, int, int]:
    valid, invalid = result
    valid_path = temp_dir / f"valid_{chunk_id:08d}.jsonl"
    invalid_path = temp_dir / f"invalid_{chunk_id:08d}.jsonl"
    with valid_path.open("w", encoding="utf-8") as f:
        for _, line in valid:
            f.write(line)
    with invalid_path.open("w", encoding="utf-8") as f:
        f.writelines(invalid)
    return valid_path, invalid_path, len(valid), len(invalid)


def merge_sorted_files(paths: list[Path], output_path: Path) -> None:
    handles = [path.open("r", encoding="utf-8") for path in paths]
    try:
        heap: list[tuple[float, int, str]] = []
        for idx, handle in enumerate(handles):
            line = handle.readline()
            if line:
                score = float(json.loads(line)["caption_similarity"])
                heapq.heappush(heap, (-score, idx, line))

        with output_path.open("w", encoding="utf-8") as out:
            while heap:
                _, idx, line = heapq.heappop(heap)
                out.write(line)
                next_line = handles[idx].readline()
                if next_line:
                    score = float(json.loads(next_line)["caption_similarity"])
                    heapq.heappush(heap, (-score, idx, next_line))
    finally:
        for handle in handles:
            handle.close()


def read_scores(path: Path, chunk_size: int = 50000) -> list[float]:
    scores: list[float] = []
    for lines in iter_line_chunks(path, chunk_size):
        for line in lines:
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                score = parse_similarity(row)
                if score is not None:
                    scores.append(score)
    return scores


def build_deciles(scores: list[float]) -> list[dict[str, Any]]:
    if not scores:
        return []
    n = len(scores)
    result: list[dict[str, Any]] = []
    for start_percent in range(0, 100, 10):
        start = n * start_percent // 100
        end = n * (start_percent + 10) // 100
        values = scores[start:end]
        if not values:
            continue
        result.append(
            {
                "rank_percent": f"{start_percent + 1}-{start_percent + 10}%",
                "rank_start": start + 1,
                "rank_end": end,
                "count": len(values),
                "similarity_max": max(values),
                "similarity_min": min(values),
                "similarity_mean": statistics.fmean(values),
            }
        )
    return result


def percentile_from_descending(scores: list[float], percentile: float) -> float:
    """Return the conventional ascending percentile from descending values."""
    idx = int((len(scores) - 1) * (100.0 - percentile) / 100.0)
    return scores[idx]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sort and analyze caption similarity JSONL.")
    parser.add_argument(
        "--input",
        default="outputs/final/pairs/2015/image_text_pairs_new_with_caption_similarity_filtered.jsonl",
    )
    parser.add_argument("--output-sorted", default="")
    parser.add_argument("--output-stats", default="")
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--chunk-size", type=int, default=50000)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"input not found: {input_path}")
    if args.workers <= 0:
        raise SystemExit("--workers must be > 0")
    if args.chunk_size <= 0:
        raise SystemExit("--chunk-size must be > 0")

    output_sorted = Path(args.output_sorted) if args.output_sorted else input_path.with_name(input_path.stem + "_sorted.jsonl")
    output_stats = Path(args.output_stats) if args.output_stats else input_path.with_name(input_path.stem + "_stats.json")
    output_sorted.parent.mkdir(parents=True, exist_ok=True)
    output_stats.parent.mkdir(parents=True, exist_ok=True)

    cpu_workers = min(args.workers, mp.cpu_count() or args.workers)
    valid_count = 0
    invalid_count = 0

    with tempfile.TemporaryDirectory(prefix="caption_similarity_") as temp_name:
        temp_dir = Path(temp_name)
        valid_paths: list[Path] = []
        invalid_paths: list[Path] = []

        chunks = iter_line_chunks(input_path, args.chunk_size)
        with ProcessPoolExecutor(max_workers=cpu_workers) as executor:
            results = executor.map(sort_chunk, chunks, chunksize=1)
            for chunk_id, result in enumerate(
                tqdm(results, desc="Sorting chunks", unit="chunk", dynamic_ncols=True)
            ):
                valid_path, invalid_path, valid_num, invalid_num = write_sorted_chunk(
                    result, temp_dir, chunk_id
                )
                valid_paths.append(valid_path)
                invalid_paths.append(invalid_path)
                valid_count += valid_num
                invalid_count += invalid_num

        merge_sorted_files(valid_paths, output_sorted)

        invalid_output = output_sorted.with_name(output_sorted.stem + "_invalid.jsonl")
        with invalid_output.open("w", encoding="utf-8") as out:
            for path in invalid_paths:
                with path.open("r", encoding="utf-8") as src:
                    for line in src:
                        out.write(line)

    scores = read_scores(output_sorted, chunk_size=args.chunk_size)
    if not scores:
        raise SystemExit("no valid caption_similarity values found")

    summary = {
        "input": str(input_path),
        "sorted_output": str(output_sorted),
        "invalid_output": str(invalid_output),
        "total_rows": valid_count + invalid_count,
        "valid_rows": valid_count,
        "invalid_rows": invalid_count,
        "invalid_ratio": invalid_count / (valid_count + invalid_count) * 100
        if valid_count + invalid_count else 0.0,
        "similarity_stats": {
            "min": min(scores),
            "max": max(scores),
            "mean": statistics.fmean(scores),
            "p01": percentile_from_descending(scores, 1),
            "p05": percentile_from_descending(scores, 5),
            "p10": percentile_from_descending(scores, 10),
            "p25": percentile_from_descending(scores, 25),
            "p50": percentile_from_descending(scores, 50),
            "p75": percentile_from_descending(scores, 75),
            "p90": percentile_from_descending(scores, 90),
            "p95": percentile_from_descending(scores, 95),
            "p99": percentile_from_descending(scores, 99),
        },
        "deciles_descending": build_deciles(scores),
        "workers": cpu_workers,
        "chunk_size": args.chunk_size,
    }
    output_stats.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Sorted output: {output_sorted}")
    print(f"Stats output: {output_stats}")
    print(f"Invalid output: {invalid_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
