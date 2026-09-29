#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from tqdm import tqdm


def percentile(sorted_values: list[int], p: float) -> int:
    if not sorted_values:
        return -1
    if p <= 0:
        return sorted_values[0]
    if p >= 100:
        return sorted_values[-1]
    idx = int((len(sorted_values) - 1) * p / 100.0)
    return sorted_values[idx]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                row = json.loads(s)
            except Exception:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def iter_success_line_chunks(source_paths: list[Path], chunk_size: int):
    chunk: list[str] = []
    for path in source_paths:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                chunk.append(line)
                if len(chunk) >= chunk_size:
                    yield chunk
                    chunk = []
    if chunk:
        yield chunk


def _worker_merge_success(lines: list[str]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for line in lines:
        s = line.strip()
        if not s:
            continue
        try:
            row = json.loads(s)
        except Exception:
            continue
        if not isinstance(row, dict):
            continue
        url = row.get("url")
        if isinstance(url, str) and url:
            rows[url] = row
    return rows


def merge_success_jsonl(input_dir: Path, merged_path: Path, workers: int, chunk_size: int) -> int:
    source_paths = sorted(
        path
        for path in input_dir.glob("*success.jsonl")
        if path.resolve() != merged_path.resolve()
    )
    if not source_paths:
        raise SystemExit(f"no success jsonl files found in: {input_dir}")

    dedup: dict[str, dict[str, Any]] = {}
    chunks = iter_success_line_chunks(source_paths, chunk_size)
    with mp.Pool(processes=workers) as pool:
        for part in tqdm(
            pool.imap_unordered(_worker_merge_success, chunks, chunksize=1),
            desc="Merging success JSONL",
            unit="chunk",
            dynamic_ncols=True,
        ):
            dedup.update(part)

    rows = sorted(
        dedup.values(),
        key=lambda row: int(row.get("idx", 0))
        if str(row.get("idx", "")).lstrip("-").isdigit()
        else 0,
    )
    write_jsonl(merged_path, rows)
    return len(rows)


def _worker_aggregate(lines: list[str]) -> dict[str, Any]:
    total = 0
    ok = 0
    fail = 0
    widths: list[int] = []
    heights: list[int] = []
    short_edges: list[int] = []
    areas: list[int] = []
    status_counter: Counter = Counter()
    reason_counter: Counter = Counter()
    domain_ok_counter: Counter = Counter()
    domain_fail_counter: Counter = Counter()
    domain_total_counter: Counter = Counter()
    timeout_rows: list[dict[str, Any]] = []

    for line in lines:
        s = line.strip()
        if not s:
            continue
        try:
            r = json.loads(s)
        except Exception:
            continue
        if not isinstance(r, dict):
            continue

        total += 1
        url = str(r.get("url", ""))
        width = int(r.get("width", -1))
        height = int(r.get("height", -1))
        # 新的 success JSONL 没有 ok 字段；能进入 success 文件即视为成功。
        ok_flag = bool(r.get("ok", True)) if "ok" in r else bool(r.get("path", ""))
        domain = str(r.get("domain", "")) or urlparse(url).netloc.lower()
        status = str(r.get("status_code", ""))
        domain_total_counter[domain] += 1
        status_counter[status] += 1

        if ok_flag:
            ok += 1
            domain_ok_counter[domain] += 1
            w = width
            h = height
            if w > 0:
                widths.append(w)
            if h > 0:
                heights.append(h)
            if w > 0 and h > 0:
                se = min(w, h)
                short_edges.append(se)
                areas.append(w * h)
        else:
            fail += 1
            domain_fail_counter[domain] += 1
            reason = str(r.get("reason", ""))
            reason_counter[reason] += 1
            if reason == "timeout":
                timeout_rows.append(r)

    return {
        "total": total,
        "ok": ok,
        "fail": fail,
        "widths": widths,
        "heights": heights,
        "short_edges": short_edges,
        "areas": areas,
        "status_counter": status_counter,
        "reason_counter": reason_counter,
        "domain_ok_counter": domain_ok_counter,
        "domain_fail_counter": domain_fail_counter,
        "domain_total_counter": domain_total_counter,
        "timeout_rows": timeout_rows,
    }


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


def parallel_aggregate(path: Path, workers: int, chunk_size: int) -> dict[str, Any]:
    total = 0
    ok = 0
    fail = 0
    widths: list[int] = []
    heights: list[int] = []
    short_edges: list[int] = []
    areas: list[int] = []
    status_counter: Counter = Counter()
    reason_counter: Counter = Counter()
    domain_ok_counter: Counter = Counter()
    domain_fail_counter: Counter = Counter()
    domain_total_counter: Counter = Counter()
    timeout_rows: list[dict[str, Any]] = []

    with mp.Pool(processes=workers) as pool:
        for part in pool.imap_unordered(_worker_aggregate, iter_line_chunks(path, chunk_size), chunksize=1):
            total += part["total"]
            ok += part["ok"]
            fail += part["fail"]
            widths.extend(part["widths"])
            heights.extend(part["heights"])
            short_edges.extend(part["short_edges"])
            areas.extend(part["areas"])
            status_counter.update(part["status_counter"])
            reason_counter.update(part["reason_counter"])
            domain_ok_counter.update(part["domain_ok_counter"])
            domain_fail_counter.update(part["domain_fail_counter"])
            domain_total_counter.update(part["domain_total_counter"])
            timeout_rows.extend(part["timeout_rows"])

    return {
        "total": total,
        "ok": ok,
        "fail": fail,
        "widths": sorted(widths),
        "heights": sorted(heights),
        "short_edges": sorted(short_edges),
        "areas": sorted(areas),
        "status_counter": status_counter,
        "reason_counter": reason_counter,
        "domain_ok_counter": domain_ok_counter,
        "domain_fail_counter": domain_fail_counter,
        "domain_total_counter": domain_total_counter,
        "timeout_rows": timeout_rows,
    }


def top_counter(counter: Counter, k: int) -> list[dict[str, Any]]:
    return [{"key": key, "count": count} for key, count in counter.most_common(k)]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Merge success JSONLs and analyze image sizes")
    parser.add_argument("--input-dir", default="outputs/final/images/2015_test")
    parser.add_argument("--merged-name", default="merged_success.jsonl")
    parser.add_argument("--output-prefix", default="")
    parser.add_argument("--topk", type=int, default=50)
    parser.add_argument("--workers", type=int, default=max(1, (mp.cpu_count() or 4) - 1))
    parser.add_argument("--merge-workers", type=int, default=16)
    parser.add_argument("--chunk-size", type=int, default=50000, help="lines per process task")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_dir = Path(args.input_dir)
    if not input_dir.is_dir():
        raise SystemExit(f"input directory not found: {input_dir}")
    if args.topk <= 0:
        raise SystemExit("--topk must be > 0")
    if args.workers <= 0:
        raise SystemExit("--workers must be > 0")
    if args.merge_workers <= 0:
        raise SystemExit("--merge-workers must be > 0")
    if args.chunk_size <= 0:
        raise SystemExit("--chunk-size must be > 0")

    input_path = input_dir / args.merged_name
    merged_count = merge_success_jsonl(
        input_dir,
        input_path,
        workers=args.merge_workers,
        chunk_size=args.chunk_size,
    )
    print(f"Merged success rows: {merged_count}")

    agg = parallel_aggregate(input_path, workers=args.workers, chunk_size=args.chunk_size)
    total = agg["total"]
    if total == 0:
        raise SystemExit("no rows found")

    ok_count = agg["ok"]
    fail_count = agg["fail"]
    widths = agg["widths"]
    heights = agg["heights"]
    short_edges = agg["short_edges"]
    areas = agg["areas"]

    short_gt_224 = sum(1 for x in short_edges if x > 224)
    short_gt_100 = sum(1 for x in short_edges if x > 100)
    short_gt_336 = sum(1 for x in short_edges if x > 336)
    short_gt_448 = sum(1 for x in short_edges if x > 448)

    status_counter = agg["status_counter"]
    reason_counter = agg["reason_counter"]
    domain_ok_counter = agg["domain_ok_counter"]
    domain_fail_counter = agg["domain_fail_counter"]
    domain_total_counter = agg["domain_total_counter"]
    timeout_rows = agg["timeout_rows"]

    domain_stats = []
    all_domains = set(domain_total_counter.keys())
    for d in all_domains:
        ok_c = domain_ok_counter.get(d, 0)
        fail_c = domain_fail_counter.get(d, 0)
        total_c = ok_c + fail_c
        domain_stats.append(
            {
                "domain": d,
                "ok": ok_c,
                "fail": fail_c,
                "total": total_c,
                "ok_ratio": (ok_c / total_c * 100) if total_c else 0.0,
            }
        )
    domain_stats.sort(key=lambda x: x["ok"], reverse=True)

    summary = {
        "input": str(input_path),
        "total_rows": total,
        "ok_rows": ok_count,
        "fail_rows": fail_count,
        "ok_ratio": (ok_count / total * 100) if total else 0.0,
        "domain_count_total": len(all_domains),
        "domain_count_with_ok": sum(1 for d in all_domains if domain_ok_counter.get(d, 0) > 0),
        "short_edge_gt_224_count": short_gt_224,
        "short_edge_gt_224_ratio_in_ok": (short_gt_224 / ok_count * 100) if ok_count else 0.0,
        "short_edge_gt_100_count": short_gt_100,
        "short_edge_gt_100_ratio_in_ok": (short_gt_100 / ok_count * 100) if ok_count else 0.0,
        "timeout_rows_count": len(timeout_rows),
        "short_edge_gt_336_count": short_gt_336,
        "short_edge_gt_336_ratio_in_ok": (short_gt_336 / ok_count * 100) if ok_count else 0.0,
        "short_edge_gt_448_count": short_gt_448,
        "short_edge_gt_448_ratio_in_ok": (short_gt_448 / ok_count * 100) if ok_count else 0.0,
        "width_stats": {
            "count": len(widths),
            "min": widths[0] if widths else -1,
            "p10": percentile(widths, 10),
            "p25": percentile(widths, 25),
            "p50": percentile(widths, 50),
            "p75": percentile(widths, 75),
            "p90": percentile(widths, 90),
            "p95": percentile(widths, 95),
            "max": widths[-1] if widths else -1,
        },
        "height_stats": {
            "count": len(heights),
            "min": heights[0] if heights else -1,
            "p10": percentile(heights, 10),
            "p25": percentile(heights, 25),
            "p50": percentile(heights, 50),
            "p75": percentile(heights, 75),
            "p90": percentile(heights, 90),
            "p95": percentile(heights, 95),
            "max": heights[-1] if heights else -1,
        },
        "short_edge_stats": {
            "count": len(short_edges),
            "min": short_edges[0] if short_edges else -1,
            "p10": percentile(short_edges, 10),
            "p25": percentile(short_edges, 25),
            "p50": percentile(short_edges, 50),
            "p75": percentile(short_edges, 75),
            "p90": percentile(short_edges, 90),
            "p95": percentile(short_edges, 95),
            "max": short_edges[-1] if short_edges else -1,
        },
        "area_stats": {
            "count": len(areas),
            "min": areas[0] if areas else -1,
            "p10": percentile(areas, 10),
            "p25": percentile(areas, 25),
            "p50": percentile(areas, 50),
            "p75": percentile(areas, 75),
            "p90": percentile(areas, 90),
            "p95": percentile(areas, 95),
            "max": areas[-1] if areas else -1,
        },
        "top_status_codes": top_counter(status_counter, args.topk),
        "top_fail_reasons": top_counter(reason_counter, args.topk),
        "top_domains_by_ok": top_counter(domain_ok_counter, args.topk),
        "top_domains_by_fail": top_counter(domain_fail_counter, args.topk),
        "top_domains_by_total": top_counter(domain_total_counter, args.topk),
        "compute_config": {
            "workers": args.workers,
            "chunk_size": args.chunk_size,
        },
    }

    prefix = Path(args.output_prefix) if args.output_prefix else input_dir / "image_size_scan_analysis"
    summary_path = prefix.with_name(prefix.name + "_summary.json")
    domain_stats_path = prefix.with_name(prefix.name + "_domain_stats.json")
    timeout_urls_path = prefix.with_name(prefix.name + "_timeout_urls.jsonl")
    report_path = prefix.with_name(prefix.name + "_report.txt")

    write_json(summary_path, summary)
    write_json(domain_stats_path, domain_stats)
    with timeout_urls_path.open("w", encoding="utf-8") as f:
        for row in timeout_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    report_lines = [
        f"Input: {input_path}",
        f"Total rows: {summary['total_rows']}",
        f"OK rows: {summary['ok_rows']} ({summary['ok_ratio']:.2f}%)",
        f"Fail rows: {summary['fail_rows']}",
        f"Total domains: {summary['domain_count_total']}",
        f"Domains with at least one accessible image: {summary['domain_count_with_ok']}",
        "",
        "Short edge thresholds (on ok rows):",
        (
            f"  >100: {summary['short_edge_gt_100_count']} "
            f"({summary['short_edge_gt_100_ratio_in_ok']:.2f}%)"
        ),
        (
            f"  >224: {summary['short_edge_gt_224_count']} "
            f"({summary['short_edge_gt_224_ratio_in_ok']:.2f}%)"
        ),
        (
            f"  >336: {summary['short_edge_gt_336_count']} "
            f"({summary['short_edge_gt_336_ratio_in_ok']:.2f}%)"
        ),
        (
            f"  >448: {summary['short_edge_gt_448_count']} "
            f"({summary['short_edge_gt_448_ratio_in_ok']:.2f}%)"
        ),
        "",
        f"Width stats: {summary['width_stats']}",
        f"Height stats: {summary['height_stats']}",
        f"Short-edge stats: {summary['short_edge_stats']}",
        f"Area stats: {summary['area_stats']}",
        "",
        "Top domains by accessible image count:",
    ]
    for x in summary["top_domains_by_ok"][:20]:
        report_lines.append(f"  {x['key']}: {x['count']}")

    report_lines.append("")
    report_lines.append("Top fail reasons:")
    for x in summary["top_fail_reasons"][:20]:
        report_lines.append(f"  {x['key']}: {x['count']}")

    report_lines.append("")
    report_lines.append("Top status codes:")
    for x in summary["top_status_codes"][:20]:
        report_lines.append(f"  {x['key']}: {x['count']}")

    write_text(report_path, "\n".join(report_lines) + "\n")

    print(f"Done. summary={summary_path}")
    print(f"Done. domain_stats={domain_stats_path}")
    print(f"Done. timeout_urls={timeout_urls_path}")
    print(f"Done. report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
