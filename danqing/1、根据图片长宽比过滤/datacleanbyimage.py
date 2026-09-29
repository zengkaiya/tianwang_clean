#!/usr/bin/env python3

from __future__ import annotations

import argparse
import io
import json
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any

import mxnet as mx
from PIL import Image
from tqdm import tqdm


Image.MAX_IMAGE_PIXELS = None


def read_jsonl(path: Path) -> list[tuple[int, dict[str, Any]]]:
    rows: list[tuple[int, dict[str, Any]]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"[warn] invalid JSON at line {line_no}: {exc}")
                continue
            if isinstance(row, dict):
                rows.append((line_no, row))
    return rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Filter JSONL image-text pairs by aspect ratio and minimum side."
    )
    parser.add_argument(
        "--input",
        default="outputs/2013_2014/images/raw/image_text_pairs_local.jsonl",
        help="Input JSONL containing local_path and caption.",
    )
    parser.add_argument(
        "--output-prefix",
        default="outputs/2013_2014/images/image_text_pairs",
        help="Output prefix for .rec/.idx/.txt.",
    )
    parser.add_argument("--min-side", type=int, default=100)
    parser.add_argument("--min-ratio", type=float, default=1 / 3)
    parser.add_argument("--max-ratio", type=float, default=3.0)
    parser.add_argument("--limit", type=int, default=0, help="Process at most N rows; 0 means all.")
    parser.add_argument("--workers", type=int, default=64, help="Image reading/validation threads.")
    parser.add_argument("--jpeg-quality", type=int, default=95, help="JPEG quality for normalized RecordIO images.")
    return parser


def prepare_image(
    item: tuple[int, dict[str, Any]],
    min_side: int,
    min_ratio: float,
    max_ratio: float,
    jpeg_quality: int,
) -> dict[str, Any]:
    line_no, row = item
    local_path = Path(str(row.get("local_path", row.get("path", ""))).strip())
    caption = str(row.get("caption", "")).strip()

    try:
        if not local_path.exists():
            raise FileNotFoundError(local_path)
        if not caption:
            raise ValueError("empty caption")

        raw_image_bytes = local_path.read_bytes()
        try:
            width = int(row.get("width", -1))
            height = int(row.get("height", -1))
        except (TypeError, ValueError):
            width = -1
            height = -1

        with Image.open(io.BytesIO(raw_image_bytes)) as image:
            if width <= 0 or height <= 0:
                width, height = image.size

            image_format = (image.format or "").upper()
            if image_format in {"JPEG", "PNG"}:
                image_bytes = raw_image_bytes
            else:
                normalized = io.BytesIO()
                image.convert("RGB").save(normalized, format="JPEG", quality=jpeg_quality)
                image_bytes = normalized.getvalue()

        if width <= 0 or height <= 0:
            raise ValueError(f"invalid image size: {width}x{height}")

        ratio = max(width, height) / min(width, height)
        shortest_side = min(width, height)
        if ratio > max_ratio or ratio < min_ratio:
            return {"ok": False, "line_no": line_no, "local_path": local_path, "reason": "ratio"}
        if shortest_side < min_side:
            return {"ok": False, "line_no": line_no, "local_path": local_path, "reason": "min_side"}

        return {
            "ok": True,
            "line_no": line_no,
            "row": row,
            "local_path": local_path,
            "caption": caption,
            "image_bytes": image_bytes,
            "width": width,
            "height": height,
        }
    except Exception as exc:  # pylint: disable=broad-except
        return {
            "ok": False,
            "line_no": line_no,
            "local_path": local_path,
            "reason": f"{type(exc).__name__}: {exc}",
        }


def main() -> int:
    args = build_parser().parse_args()
    input_path = Path(args.input)
    output_prefix = Path(args.output_prefix)

    if not input_path.exists():
        raise SystemExit(f"input not found: {input_path}")
    if args.min_side < 1:
        raise SystemExit("--min-side must be positive")
    if args.min_ratio <= 0 or args.max_ratio < args.min_ratio:
        raise SystemExit("invalid ratio range")
    if args.limit < 0:
        raise SystemExit("--limit must be >= 0")
    if args.workers <= 0:
        raise SystemExit("--workers must be > 0")
    if not 1 <= args.jpeg_quality <= 100:
        raise SystemExit("--jpeg-quality must be between 1 and 100")

    rows = read_jsonl(input_path)
    if args.limit:
        rows = rows[: args.limit]

    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    rec_path = output_prefix.with_suffix(".rec")
    idx_path = output_prefix.with_suffix(".idx")
    txt_path = output_prefix.with_suffix(".txt")
    manifest_path = output_prefix.with_name(output_prefix.name + "_manifest.jsonl")

    writer = mx.recordio.MXIndexedRecordIO(str(idx_path), str(rec_path), "w")
    total = len(rows)
    kept = 0
    skipped = 0

    try:
        with txt_path.open("w", encoding="utf-8") as txt_f, \
             manifest_path.open("w", encoding="utf-8") as manifest_f, \
             ThreadPoolExecutor(max_workers=args.workers) as executor:
            row_iter = iter(rows)
            pending: dict[Any, tuple[int, dict[str, Any]]] = {}

            for _ in range(args.workers * 2):
                try:
                    item = next(row_iter)
                except StopIteration:
                    break
                future = executor.submit(
                    prepare_image,
                    item,
                    args.min_side,
                    args.min_ratio,
                    args.max_ratio,
                    args.jpeg_quality,
                )
                pending[future] = item

            with tqdm(total=total, desc="Filtering images", unit="img", dynamic_ncols=True) as progress:
                while pending:
                    done, _ = wait(pending, return_when=FIRST_COMPLETED)
                    for future in done:
                        result = future.result()
                        pending.pop(future, None)
                        progress.update(1)

                        if not result["ok"]:
                            skipped += 1
                        else:
                            image_bytes = result["image_bytes"]
                            header = mx.recordio.IRHeader(
                                flag=0,
                                label=1.0,
                                id=result["line_no"],
                                id2=0,
                            )
                            writer.write_idx(kept, mx.recordio.pack(header, image_bytes))
                            txt_f.write(result["caption"] + "\n")

                            output_row = dict(result["row"])
                            output_row["record_idx"] = kept
                            output_row["width"] = result["width"]
                            output_row["height"] = result["height"]
                            manifest_f.write(json.dumps(output_row, ensure_ascii=False) + "\n")
                            kept += 1

                        try:
                            item = next(row_iter)
                        except StopIteration:
                            continue
                        next_future = executor.submit(
                            prepare_image,
                            item,
                            args.min_side,
                            args.min_ratio,
                            args.max_ratio,
                            args.jpeg_quality,
                        )
                        pending[next_future] = item
    finally:
        writer.close()

    print(f"Input rows: {total}")
    print(f"Kept rows: {kept}")
    print(f"Skipped rows: {skipped}")
    print(f"RecordIO: {rec_path}")
    print(f"Index: {idx_path}")
    print(f"Text: {txt_path}")
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
