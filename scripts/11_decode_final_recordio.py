#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import sys
from pathlib import Path

import mxnet as mx
from tqdm import tqdm


_WORKER_READER = None
_WORKER_TOKENIZER = None


def load_bert_tokenizer():
    tokenizer_path = Path(__file__).resolve().parents[1] / "cn-clip-ctp/src"
    sys.path.insert(0, str(tokenizer_path))
    from open_clip.bert_tokenizer import _tokenizer

    return _tokenizer


def decode_text(label, tokenizer) -> str:
    token_ids = [int(token_id) for token_id in label[:52] if int(token_id) != 0]
    tokens = tokenizer.convert_ids_to_tokens(token_ids)
    text = "".join(tokens)
    return (
        text.replace("[CLS]", "")
        .replace("[SEP]", "")
        .replace("[PAD]", "")
        .replace("[UNK]", "")
        .replace("#", "")
        .strip()
    )


def init_worker(input_prefix: str) -> None:
    global _WORKER_READER, _WORKER_TOKENIZER
    _WORKER_READER = mx.recordio.MXIndexedRecordIO(
        str(Path(input_prefix).with_suffix(".idx")),
        str(Path(input_prefix).with_suffix(".rec")),
        "r",
    )
    _WORKER_TOKENIZER = load_bert_tokenizer()


def process_chunk(args: tuple[int, str, str, int, int, list[int]]) -> int:
    chunk_id, image_dir, part_dir, start_index, bucket_size, record_keys = args
    reader = _WORKER_READER
    tokenizer = _WORKER_TOKENIZER
    Path(image_dir).mkdir(parents=True, exist_ok=True)
    Path(part_dir).mkdir(parents=True, exist_ok=True)

    captions_path = Path(part_dir) / f"captions_{chunk_id:08d}.txt"
    manifest_path = Path(part_dir) / f"manifest_{chunk_id:08d}.jsonl"

    with captions_path.open("w", encoding="utf-8") as captions_file, manifest_path.open(
        "w", encoding="utf-8"
    ) as manifest_file:
        for offset, record_key in enumerate(record_keys):
            output_index = start_index + offset
            packed = reader.read_idx(record_key)
            header, image_bytes = mx.recordio.unpack(packed)
            text = decode_text(header.label, tokenizer)

            bucket_index = (output_index - 1) // bucket_size
            bucket_start = bucket_index * bucket_size + 1
            bucket_end = (bucket_index + 1) * bucket_size
            bucket_dir = Path(image_dir) / f"{bucket_start:09d}-{bucket_end:09d}"
            bucket_dir.mkdir(parents=True, exist_ok=True)
            image_path = bucket_dir / f"{output_index:09d}.jpg"
            image_path.write_bytes(image_bytes)
            captions_file.write(text + "\n")
            manifest_file.write(
                json.dumps(
                    {
                        "idx": output_index,
                        "record_key": int(record_key),
                        "image": str(image_path),
                        "caption": text,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    return len(record_keys)


def main() -> int:
    parser = argparse.ArgumentParser(description="Decode MXNet RecordIO into images and text.")
    parser.add_argument("--input-prefix", default="outputs/2013_2014/danqing/final")
    parser.add_argument("--output-dir", default="outputs/2013_2014/danqing/final_decoded")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--chunk-size", type=int, default=5000)
    parser.add_argument("--bucket-size", type=int, default=20000)
    args = parser.parse_args()

    if args.workers <= 0:
        raise SystemExit("--workers must be > 0")
    if args.chunk_size <= 0:
        raise SystemExit("--chunk-size must be > 0")
    if args.bucket_size <= 0:
        raise SystemExit("--bucket-size must be > 0")

    input_prefix = Path(args.input_prefix)
    output_dir = Path(args.output_dir)
    image_dir = output_dir / "images"
    part_dir = output_dir / ".parts"
    image_dir.mkdir(parents=True, exist_ok=True)
    part_dir.mkdir(parents=True, exist_ok=True)

    reader = mx.recordio.MXIndexedRecordIO(
        str(input_prefix.with_suffix(".idx")),
        str(input_prefix.with_suffix(".rec")),
        "r",
    )
    record_keys = list(reader.keys)
    reader.close()
    total_records = len(record_keys)
    if total_records == 0:
        raise SystemExit("no records found")

    jobs: list[tuple[int, str, str, int, int, list[int]]] = []
    for chunk_id, start in enumerate(range(0, total_records, args.chunk_size)):
        keys = record_keys[start : start + args.chunk_size]
        jobs.append(
            (
                chunk_id,
                str(image_dir),
                str(part_dir),
                start + 1,
                args.bucket_size,
                keys,
            )
        )

    worker_count = min(args.workers, mp.cpu_count() or args.workers)
    counts: list[int] = []
    with mp.Pool(
        worker_count,
        initializer=init_worker,
        initargs=(str(input_prefix),),
    ) as pool:
        for count in tqdm(
            pool.imap_unordered(process_chunk, jobs),
            total=len(jobs),
            desc="Decoding chunks",
            unit="chunk",
            dynamic_ncols=True,
        ):
            counts.append(count)

    captions_path = output_dir / "captions.txt"
    manifest_path = output_dir / "manifest.jsonl"
    with captions_path.open("w", encoding="utf-8") as captions_file, manifest_path.open(
        "w", encoding="utf-8"
    ) as manifest_file:
        for chunk_id in range(len(jobs)):
            captions_part = part_dir / f"captions_{chunk_id:08d}.txt"
            manifest_part = part_dir / f"manifest_{chunk_id:08d}.jsonl"
            if captions_part.exists():
                captions_file.write(captions_part.read_text(encoding="utf-8"))
                captions_part.unlink()
            if manifest_part.exists():
                manifest_file.write(manifest_part.read_text(encoding="utf-8"))
                manifest_part.unlink()

    try:
        part_dir.rmdir()
    except OSError:
        pass

    print(f"Records: {total_records}")
    print(f"Images: {image_dir}")
    print(f"Captions: {captions_path}")
    print(f"Manifest: {manifest_path}")
    print(f"Workers: {worker_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
