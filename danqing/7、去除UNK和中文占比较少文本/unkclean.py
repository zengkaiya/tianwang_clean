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
from cn_clip_tokenizer import _tokenizer, tokenize

output_dir = os.environ.get("DANQING_OUTPUT_DIR", "outputs/final/danqing/2015_v2")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Remove UNK tokens and rewrite RecordIO labels.")
    parser.add_argument("--input-idx", default=f"{output_dir}/clean_unk_words.idx")
    parser.add_argument("--input-rec", default=f"{output_dir}/clean_unk_words.rec")
    parser.add_argument("--output-idx", default=f"{output_dir}/final.idx")
    parser.add_argument("--output-rec", default=f"{output_dir}/final.rec")
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--token-workers", type=int, default=8)
    parser.add_argument("--prefetch-batches", type=int, default=2)
    parser.add_argument("--target-length", type=int, default=52)
    return parser


def clean_text(label: Any) -> str:
    token_ids = label[:52]
    text_char_list = _tokenizer.convert_ids_to_tokens(token_ids)
    text_raw = "".join(text_char_list).split("[PAD]")[0]
    return (
        text_raw
        .replace("[CLS]", "")
        .replace("[SEP]", "")
        .replace("[PAD]", "")
        .replace("#", "")
        .replace("[UNK]", "")
        .strip()
    )


def tokenize_batch(texts: list[str], target_length: int):
    return tokenize(texts, context_length=target_length).numpy()


def init_token_worker() -> None:
    torch.set_num_threads(1)


def read_batch(
    rec_reader: mx.recordio.MXIndexedRecordIO,
    keys: list[int],
    start: int,
    batch_size: int,
) -> tuple[list[bytes], list[str]]:
    image_bytes: list[bytes] = []
    cleaned_texts: list[str] = []
    end = min(start + batch_size, len(keys))
    for pos in range(start, end):
        packed = rec_reader.read_idx(keys[pos])
        header, jpeg = mx.recordio.unpack(packed)
        image_bytes.append(jpeg)
        cleaned_texts.append(clean_text(header.label))
    return image_bytes, cleaned_texts


def extract_and_clean_from_rec(
    in_idx: str,
    in_rec: str,
    out_idx: str,
    out_rec: str,
    batch_size: int = 512,
    token_workers: int = 8,
    prefetch_batches: int = 2,
    target_length: int = 52,
) -> None:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    if token_workers <= 0:
        raise ValueError("token_workers must be positive")
    if prefetch_batches <= 0:
        raise ValueError("prefetch_batches must be positive")

    Path(out_idx).parent.mkdir(parents=True, exist_ok=True)
    rec_reader = mx.recordio.MXIndexedRecordIO(in_idx, in_rec, "r")
    keys = sorted(rec_reader.keys)
    total_num = len(keys)
    if total_num == 0:
        rec_reader.close()
        raise ValueError("no records found")

    writer = mx.recordio.MXIndexedRecordIO(out_idx, out_rec, "w")
    pending: deque[tuple[Any, list[bytes]]] = deque()
    next_start = 0
    output_index = 0

    try:
        with tqdm(total=total_num, desc="Cleaning and tokenizing", unit="row", dynamic_ncols=True) as progress, \
             ProcessPoolExecutor(
                 max_workers=token_workers,
                 initializer=init_token_worker,
             ) as executor:
            while next_start < total_num or pending:
                while next_start < total_num and len(pending) < token_workers * prefetch_batches:
                    image_bytes, texts = read_batch(
                        rec_reader,
                        keys,
                        next_start,
                        batch_size,
                    )
                    future = executor.submit(tokenize_batch, texts, target_length)
                    pending.append((future, image_bytes))
                    next_start += len(texts)

                if not pending:
                    continue

                future, image_bytes = pending.popleft()
                labels = future.result()
                for jpeg, label in zip(image_bytes, labels):
                    header = mx.recordio.IRHeader(flag=0, label=label, id=0, id2=0)
                    writer.write_idx(output_index, mx.recordio.pack(header, jpeg))
                    output_index += 1
                progress.update(len(image_bytes))
    finally:
        writer.close()
        rec_reader.close()

    print(f"Input rows: {total_num}")
    print(f"Output rows: {output_index}")
    print(f"Output RecordIO: {out_rec}")


def main() -> int:
    args = build_parser().parse_args()
    extract_and_clean_from_rec(
        in_idx=args.input_idx,
        in_rec=args.input_rec,
        out_idx=args.output_idx,
        out_rec=args.output_rec,
        batch_size=args.batch_size,
        token_workers=args.token_workers,
        prefetch_batches=args.prefetch_batches,
        target_length=args.target_length,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
