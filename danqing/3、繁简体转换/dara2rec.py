#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import sys
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import mxnet as mx
import torch
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cn_clip_tokenizer import tokenize

output_dir = os.environ.get("DANQING_OUTPUT_DIR", "outputs/final/danqing/2015_v2")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert captions to token labels and write MXNet RecordIO.")
    parser.add_argument("--raw-idx", default=f"{output_dir}/jiebaclean.idx")
    parser.add_argument("--raw-rec", default=f"{output_dir}/jiebaclean.rec")
    parser.add_argument("--text", default=f"{output_dir}/jiebaclean2simple.txt")
    parser.add_argument("--output-prefix", default=f"{output_dir}/simple")
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--token-workers", type=int, default=8)
    parser.add_argument("--prefetch-batches", type=int, default=2)
    parser.add_argument("--target-length", type=int, default=52)
    return parser


def tokenize_batch(texts: list[str], target_length: int):
    return tokenize(texts, context_length=target_length).numpy()


def init_token_worker() -> None:
    # 避免每个 tokenizer 进程内部再启动多线程，减少 CPU 过度竞争。
    torch.set_num_threads(1)


def read_batch(
    rec_data: mx.recordio.MXIndexedRecordIO,
    text_data: list[str],
    start: int,
    batch_size: int,
) -> tuple[list[bytes], list[str]]:
    image_bytes: list[bytes] = []
    captions: list[str] = []
    end = min(start + batch_size, len(text_data))
    for idx in range(start, end):
        packed = rec_data.read_idx(idx)
        _, jpeg = mx.recordio.unpack(packed)
        image_bytes.append(jpeg)
        captions.append(text_data[idx].strip().lower())
    return image_bytes, captions


def main() -> int:
    args = build_parser().parse_args()
    if args.batch_size <= 0:
        raise SystemExit("--batch-size must be > 0")
    if args.token_workers <= 0:
        raise SystemExit("--token-workers must be > 0")
    if args.prefetch_batches <= 0:
        raise SystemExit("--prefetch-batches must be > 0")
    if args.target_length <= 0:
        raise SystemExit("--target-length must be > 0")

    output_prefix = Path(args.output_prefix)
    output_prefix.parent.mkdir(parents=True, exist_ok=True)

    rec_data = mx.recordio.MXIndexedRecordIO(args.raw_idx, args.raw_rec, "r")
    with open(args.text, "r", encoding="utf-8") as text_file:
        text_data = text_file.readlines()

    total_num = min(len(rec_data.keys), len(text_data))
    if total_num == 0:
        rec_data.close()
        raise SystemExit("no records found")
    if len(rec_data.keys) != len(text_data):
        print(
            f"Warning: record count={len(rec_data.keys)} differs from text count={len(text_data)}; "
            f"processing first {total_num} rows."
        )

    record = mx.recordio.MXIndexedRecordIO(
        str(output_prefix) + ".idx",
        str(output_prefix) + ".rec",
        "w",
    )

    pending: deque[tuple[Any, list[bytes]]] = deque()
    next_start = 0
    written = 0

    try:
        with tqdm(total=total_num, desc="Tokenizing and writing", unit="row", dynamic_ncols=True) as progress, \
             ProcessPoolExecutor(
                 max_workers=args.token_workers,
                 initializer=init_token_worker,
             ) as executor:
            while next_start < total_num or pending:
                while next_start < total_num and len(pending) < args.token_workers * args.prefetch_batches:
                    image_bytes, captions = read_batch(
                        rec_data,
                        text_data,
                        next_start,
                        args.batch_size,
                    )
                    future = executor.submit(tokenize_batch, captions, args.target_length)
                    pending.append((future, image_bytes))
                    next_start += len(captions)

                if not pending:
                    continue

                future, image_bytes = pending.popleft()
                labels = future.result()
                for jpeg, label in zip(image_bytes, labels):
                    header = mx.recordio.IRHeader(flag=0, label=label, id=0, id2=0)
                    record.write_idx(written, mx.recordio.pack(header, jpeg))
                    written += 1

                progress.update(len(image_bytes))
    finally:
        record.close()
        rec_data.close()

    print(f"Done. Input rows: {total_num}")
    print(f"Written rows: {written}")
    print(f"Output prefix: {output_prefix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
