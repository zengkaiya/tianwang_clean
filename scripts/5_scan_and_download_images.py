#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import mimetypes
import socket
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from PIL import Image
import requests
from tqdm import tqdm


IMAGE_EXT_BY_FORMAT = {
    "JPEG": ".jpg",
    "JPG": ".jpg",
    "PNG": ".png",
    "GIF": ".gif",
    "WEBP": ".webp",
    "BMP": ".bmp",
    "TIFF": ".tiff",
    "ICO": ".ico",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def load_done_urls(paths: list[Path]) -> set[str]:
    done: set[str] = set()
    for path in paths:
        for row in read_jsonl(path):
            url = row.get("url")
            if isinstance(url, str) and url:
                done.add(url)
    return done


class DownloadFailure(RuntimeError):
    def __init__(self, status_code: int, reason: str) -> None:
        super().__init__(reason)
        self.status_code = status_code
        self.reason = reason


_THREAD_LOCAL = threading.local()


def get_http_session(user_agent: str) -> requests.Session:
    session = getattr(_THREAD_LOCAL, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": "image/*,*/*;q=0.1",
            }
        )
        _THREAD_LOCAL.session = session
    return session


def infer_ext(url: str, content_type: str, image_format: str | None) -> str:
    if image_format:
        ext = IMAGE_EXT_BY_FORMAT.get(image_format.upper(), "")
        if ext:
            return ext
    if content_type:
        ext = mimetypes.guess_extension(content_type.split(";", 1)[0].strip().lower()) or ""
        if ext in {".jpe", ".jpeg"}:
            return ".jpg"
        if ext:
            return ext
    path_ext = Path(urlparse(url).path).suffix.lower()
    if path_ext in {".jpe", ".jpeg"}:
        return ".jpg"
    return path_ext if path_ext and len(path_ext) <= 8 else ".jpg"


def bucket_dir(output_root: Path, image_id: int, bucket_size: int) -> Path:
    bucket_idx = ((image_id - 1) // bucket_size) + 1
    start = (bucket_idx - 1) * bucket_size + 1
    end = bucket_idx * bucket_size
    return output_root / f"{start:09d}-{end:09d}"


def save_bytes_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def download_and_inspect(
    url: str,
    timeout: float,
    user_agent: str,
    max_retries: int,
) -> tuple[int, bytes, str, str, tuple[int, int]]:
    attempts = max(1, max_retries + 1)
    last_status_code = -1
    last_error = "download_failed"

    for attempt in range(attempts):
        try:
            session = get_http_session(user_agent)
            resp = session.get(url, timeout=timeout)
            status_code = int(resp.status_code)
            content_type = (resp.headers.get("Content-Type", "") or "").strip()
            if status_code >= 400:
                last_status_code = status_code
                last_error = f"HTTPError:{status_code}"
                if status_code not in (408, 429) and status_code < 500:
                    break
                raise requests.HTTPError(last_error)
            data = resp.content

            with Image.open(BytesIO(data)) as image:
                image_format = image.format or ""
                width, height = image.size
                image.verify()

            return status_code, data, content_type, image_format, (width, height)
        except (requests.Timeout, socket.timeout):
            last_status_code = -1
            last_error = "timeout"
        except requests.RequestException as exc:
            if last_status_code >= 400:
                last_error = str(exc)
            else:
                last_status_code = -1
                last_error = f"{type(exc).__name__}:{exc}"
        except OSError as exc:
            last_status_code = -1
            last_error = f"{type(exc).__name__}:{exc}"
        except Exception as exc:  # pylint: disable=broad-except
            last_status_code = -1
            last_error = f"{type(exc).__name__}:{exc}"

        if attempt + 1 < attempts:
            time.sleep(min(2.0, 0.3 * (attempt + 1)))

    raise DownloadFailure(last_status_code, last_error)


def worker_download(
    job: dict[str, Any],
    output_root: Path,
    bucket_size: int,
    timeout: float,
    user_agent: str,
    max_retries: int,
) -> dict[str, Any]:
    url = str(job["url"])
    status_code, data, content_type, image_format, size = download_and_inspect(
        url=url,
        timeout=timeout,
        user_agent=user_agent,
        max_retries=max_retries,
    )
    ext = infer_ext(url, content_type, image_format)
    local_path = bucket_dir(output_root, int(job["image_id"]), bucket_size) / f"{int(job['image_id']):09d}{ext}"
    save_bytes_atomic(local_path, data)

    result = dict(job)
    result.update(
        {
            "path": str(local_path),
            "ok": True,
            "status_code": status_code,
            "reason": "",
            "local_path": str(local_path),
            "content_type": content_type,
            "image_format": image_format,
            "width": size[0],
            "height": size[1],
            "image_width": size[0],
            "image_height": size[1],
        }
    )
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan and download images from accessible domains.")
    parser.add_argument("--accessible-domains", default="outputs/2013_2014/domain_scan_accessible_domains.json")
    parser.add_argument("--domain-urls", default="outputs/2013_2014/image_scan_domain_urls.json")
    parser.add_argument("--output-prefix", default="outputs/2013_2014/image_scan_download")
    parser.add_argument("--output", default="", help="deprecated alias; used as the output prefix")
    parser.add_argument("--output-root", default="outputs/2013_2014/images")
    parser.add_argument("--workers", type=int, default=64)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--user-agent", default="Mozilla/5.0 (compatible; TianWangImageDownloader/1.0)")
    parser.add_argument("--max-urls", type=int, default=0, help="for debug; 0 means all")
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--splits", type=int, default=1, help="split pending urls into N parts")
    parser.add_argument("--index", type=int, default=1, help="1-based split index to download")
    parser.add_argument("--save-every", type=int, default=1000)
    parser.add_argument("--bucket-size", type=int, default=5000)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.workers <= 0:
        raise SystemExit("--workers must be > 0")
    if args.timeout <= 0:
        raise SystemExit("--timeout must be > 0")
    if args.max_urls < 0:
        raise SystemExit("--max-urls must be >= 0")
    if args.max_retries < 0:
        raise SystemExit("--max-retries must be >= 0")
    if args.splits <= 0:
        raise SystemExit("--splits must be > 0")
    if args.index <= 0 or args.index > args.splits:
        raise SystemExit("--index must be between 1 and --splits")
    if args.save_every <= 0:
        raise SystemExit("--save-every must be > 0")
    if args.bucket_size <= 0:
        raise SystemExit("--bucket-size must be > 0")

    accessible_domains = set(read_json(Path(args.accessible_domains)))
    domain_urls = read_json(Path(args.domain_urls))
    if not isinstance(domain_urls, dict):
        raise SystemExit("domain urls json format invalid")

    urls: list[str] = []
    domain_counts: dict[str, int] = {}
    for domain, payload in domain_urls.items():
        if domain not in accessible_domains:
            continue
        if isinstance(payload, list):
            domain_list = payload
        elif isinstance(payload, dict):
            domain_list = payload.get("urls", [])
        else:
            continue
        if not isinstance(domain_list, list):
            continue
        domain_counts[domain] = len(domain_list)
        urls.extend(str(url).strip() for url in domain_list if isinstance(url, str) and url.strip())

    urls = sorted(set(urls))
    if args.max_urls > 0:
        urls = urls[: args.max_urls]

    prefix = Path(args.output) if args.output else Path(args.output_prefix)
    if prefix.suffix == ".jsonl":
        prefix = prefix.with_suffix("")
    success_path = prefix.with_name(prefix.name + "_success.jsonl")
    failure_path = prefix.with_name(prefix.name + "_failure.jsonl")
    summary_path = prefix.with_name(prefix.name + "_summary.jsonl")
    output_root = Path(args.output_root)

    output_paths = [success_path, failure_path, summary_path]
    done_urls = load_done_urls([success_path, failure_path]) if args.resume else set()
    split_urls = [
        url
        for position, url in enumerate(urls)
        if position % args.splits == args.index - 1
    ]
    pending_urls = [url for url in split_urls if url not in done_urls]
    if not args.resume:
        for path in output_paths:
            if path.exists():
                path.unlink()

    print(f"Accessible domains: {len(accessible_domains)}")
    print(f"Domains in scan set: {len(domain_counts)}")
    print(f"Unique urls total: {len(urls)}")
    print(f"Already done (resume): {len(done_urls)}")
    print(f"Current split: {args.index}/{args.splits}")
    print(f"Urls assigned to current split: {len(split_urls)}")
    print(f"Pending urls to download: {len(pending_urls)}")

    pending_set = set(pending_urls)
    jobs = [
        {
            "image_id": image_id,
            "source_idx": image_id - 1,
            "url": url,
            "domain": urlparse(url).netloc.lower(),
        }
        for image_id, url in enumerate(urls, start=1)
        if url in pending_set
    ]

    batch_success: list[dict[str, Any]] = []
    batch_failure: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        future_to_job = {
            ex.submit(
                worker_download,
                job,
                output_root,
                args.bucket_size,
                args.timeout,
                args.user_agent,
                args.max_retries,
            ): job
            for job in jobs
        }
        for fu in tqdm(
            as_completed(future_to_job),
            total=len(future_to_job),
            desc="Downloading images",
            unit="img",
            dynamic_ncols=True,
        ):
            job = future_to_job[fu]
            try:
                row = fu.result()
                batch_success.append(
                    {
                        "idx": row["image_id"],
                        "url": row["url"],
                        "path": row["path"],
                        "width": row["width"],
                        "height": row["height"],
                    }
                )
            except DownloadFailure as exc:
                batch_failure.append(
                    {
                        "idx": job["image_id"],
                        "url": job["url"],
                        "status_code": exc.status_code,
                        "reason": exc.reason,
                    }
                )
            except Exception as exc:  # pylint: disable=broad-except
                batch_failure.append(
                    {
                        "idx": job["image_id"],
                        "url": job["url"],
                        "status_code": -1,
                        "reason": f"{type(exc).__name__}:{exc}",
                    }
                )
            if len(batch_success) + len(batch_failure) >= args.save_every:
                append_jsonl(success_path, batch_success)
                append_jsonl(failure_path, batch_failure)
                batch_success = []
                batch_failure = []
        append_jsonl(success_path, batch_success)
        append_jsonl(failure_path, batch_failure)

    success_by_url = {row["url"]: row for row in read_jsonl(success_path) if isinstance(row.get("url"), str)}
    failure_by_url = {row["url"]: row for row in read_jsonl(failure_path) if isinstance(row.get("url"), str)}
    success_rows = list(success_by_url.values())
    failure_rows = list(failure_by_url.values())

    reason_counter = Counter(str(row.get("reason", "")) for row in failure_rows)
    summary_row = {
        "total_urls": len(success_rows) + len(failure_rows),
        "success_urls": len(success_rows),
        "failure_urls": len(failure_rows),
        "success_ratio": (len(success_rows) / (len(success_rows) + len(failure_rows)) * 100)
        if success_rows or failure_rows else 0.0,
        "accessible_domain_count": len(accessible_domains),
        "scanned_domain_count": len(domain_counts),
        "resume_enabled": args.resume,
        "resume_done_urls": len(done_urls),
        "split_urls": len(split_urls),
        "pending_urls_in_this_run": len(pending_urls),
        "splits": args.splits,
        "index": args.index,
        "workers": args.workers,
        "max_retries": args.max_retries,
        "failure_reasons": dict(reason_counter),
    }
    write_jsonl(summary_path, [summary_row])

    print(f"Done. success={len(success_rows)}/{summary_row['total_urls']}")
    print(f"Success: {success_path}")
    print(f"Failure: {failure_path}")
    print(f"Summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
