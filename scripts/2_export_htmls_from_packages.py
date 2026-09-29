#!/usr/bin/env python3

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import mimetypes
import re
import sys
import time
import zlib
from pathlib import Path
from urllib.parse import urlparse

from tqdm import tqdm


HEADER_RE = re.compile(r"^([^:]+):\s*(.*)$")


def decode_text(value: bytes) -> str:
    for encoding in ("utf-8", "gb18030", "latin1"):
        try:
            return value.decode(encoding)
        except UnicodeDecodeError:
            continue
    return value.decode("latin1", errors="ignore")


def parse_headers_block(stream):
    headers = {}
    while True:
        line = stream.readline()
        if line == b"":
            return None if not headers else headers
        if line in (b"\n", b"\r\n"):
            continue
        match = HEADER_RE.match(decode_text(line).rstrip("\r\n"))
        if not match:
            continue
        key, value = match.group(1), match.group(2)
        headers[key] = value
        if key == "length":
            return headers


def parse_http_reply(reply_bytes: bytes) -> tuple[list[str], bytes]:
    for separator in (b"\r\n\r\n", b"\n\n"):
        if separator in reply_bytes:
            head, body = reply_bytes.split(separator, 1)
            lines = [decode_text(line).rstrip("\r\n") for line in head.splitlines()]
            return lines, body
    return [], b""


def infer_extension(url: str, headers: list[str]) -> str:
    content_type = ""
    for header in headers:
        if header.lower().startswith("content-type:"):
            content_type = header.split(":", 1)[1].split(";", 1)[0].strip().lower()
            break
    extension = mimetypes.guess_extension(content_type) if content_type else None
    if extension is None:
        extension = Path(urlparse(url).path).suffix or ".html"
    return extension.lstrip(".").lower()


def parse_package(package_path: Path, output_dir: Path) -> int:
    html_index = 0
    with package_path.open("rb") as stream:
        while True:
            meta = parse_headers_block(stream)
            if meta is None:
                break
            try:
                length = int(meta.get("length", "-1"))
            except ValueError:
                break
            if length < 0:
                break

            stream.readline()
            reply_bytes = stream.read(length)
            if len(reply_bytes) < length:
                break

            if meta.get("unzip-length") is not None:
                try:
                    reply_bytes = zlib.decompress(reply_bytes)
                except zlib.error:
                    pass

            headers, body = parse_http_reply(reply_bytes)
            if infer_extension(meta.get("url", ""), headers) != "html":
                continue

            html_index += 1
            bucket = ((html_index - 1) // 10000) + 1
            target_dir = output_dir / str(bucket)
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / f"{html_index}.html").write_bytes(body)

    return html_index


def process_package(data_root: str, output_root: str, row: str) -> tuple[str, int, str | None]:
    repo_path = row.split("\t")[-1]
    package_path = Path(data_root) / repo_path
    if not package_path.is_file():
        return repo_path, 0, str(package_path)

    package_output = Path(output_root) / Path(repo_path)
    count = parse_package(package_path, package_output)
    return repo_path, count, None


def main() -> int:
    parser = argparse.ArgumentParser(description="Export all HTML samples from selected TianWang packages.")
    parser.add_argument("--package-list", required=True)
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--jobs", type=int, default=1)
    args = parser.parse_args()

    package_list = Path(args.package_list)
    data_root = Path(args.data_root)
    output_root = Path(args.output_root)
    rows = [line.strip() for line in package_list.read_text(encoding="utf-8").splitlines() if line.strip()]

    if args.jobs <= 0:
        raise SystemExit("--jobs must be positive")

    html_count = 0
    missing = 0
    package_counts = {}
    with cf.ProcessPoolExecutor(max_workers=args.jobs) as executor:
        futures = [
            executor.submit(process_package, str(data_root), str(output_root), row)
            for row in rows
        ]
        for future in tqdm(cf.as_completed(futures), total=len(futures), desc="Packages", unit="package"):
            repo_path, count, missing_path = future.result()
            if missing_path is not None:
                print(f"[missing] {missing_path}", file=sys.stderr)
                missing += 1
                continue
            html_count += count
            package_counts[Path(repo_path).name] = count
            print(f"[done] {repo_path}: html={count}", flush=True)

    counts_path = output_root / "html_counts.json"
    counts_path.write_text(
        json.dumps(dict(sorted(package_counts.items())), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"HTML files: {html_count}")
    print(f"Package HTML counts: {counts_path}")
    if missing:
        print(f"Missing packages: {missing}", file=sys.stderr)
    print(f"Output root: {output_root}")
    return 0 if missing == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
