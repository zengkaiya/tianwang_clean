#!/usr/bin/env python3

from __future__ import annotations

import argparse
from functools import lru_cache
import json
import re
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterator
from urllib.parse import urljoin, urlparse

from tqdm import tqdm

try:
    from selectolax.parser import HTMLParser as SelectolaxHTMLParser
except ImportError:
    SelectolaxHTMLParser = None

try:
    from lxml import html as lxml_html
except ImportError:
    lxml_html = None

DEFAULT_IMAGE_BLACKLIST = ("logo", "icon", "ads", "banner", "sprite", "avatar")
VALID_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".svg", ".avif")


@dataclass
class TaskResult:
    html_path: str
    ok: bool
    image_count: int
    domains: list[str]
    image_urls: list[str]
    error: str = ""


def load_html_counts(counts_path: Path) -> dict[str, int]:
    try:
        raw_counts = json.loads(counts_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid html counts JSON: {counts_path}") from exc

    if not isinstance(raw_counts, dict):
        raise ValueError("html counts JSON must be an object")

    counts = {}
    for package_name, count in raw_counts.items():
        if not isinstance(package_name, str) or not isinstance(count, int) or count < 0:
            raise ValueError(f"invalid package count: {package_name}: {count}")
        counts[package_name] = count
    return counts


def iter_html_paths(counts_path: Path, html_root: Path) -> Iterator[Path]:
    year = counts_path.parent.name
    counts = load_html_counts(counts_path)
    for package_name, count in counts.items():
        match = re.search(r"Web_Raw\.([A-Za-z]\d{6})\.", package_name)
        if match is None:
            raise ValueError(f"cannot infer month directory: {package_name}")

        month_dir = match.group(1)
        for index in range(1, count + 1):
            bucket = (index - 1) // 10000 + 1
            yield (
                html_root
                / year
                / month_dir
                / package_name
                / str(bucket)
                / f"{index}.html"
            )


def clean_image_url(raw_url: str) -> str:
    if not raw_url:
        return ""
    u = raw_url.strip().strip('"').strip("'")
    if not u:
        return ""
    if u.startswith("//"):
        return "https:" + u
    if u.lower().startswith("data:"):
        return ""
    if u.lower().startswith("javascript:"):
        return ""
    return u


@lru_cache(maxsize=200_000)
def get_ext_from_url(url: str) -> str:
    path = urlparse(url).path.lower()
    for ext in VALID_IMAGE_EXTS:
        if path.endswith(ext):
            return ext
    return ""


def is_valid_image_url(url: str, blacklist_keywords: tuple[str, ...], strict_ext: bool) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    if get_ext_from_url(url) == ".gif":
        return False
    ul = url.lower()
    if any(k in ul for k in blacklist_keywords):
        return False
    if strict_ext and not get_ext_from_url(url):
        return False
    return True


@lru_cache(maxsize=500_000)
def resolve_and_validate_url(
    raw_url: str,
    effective_base_url: str,
    blacklist_keywords: tuple[str, ...],
    strict_ext: bool,
) -> str:
    cleaned = clean_image_url(raw_url)
    if not cleaned:
        return ""
    resolved = urljoin(effective_base_url, cleaned) if effective_base_url else cleaned
    return resolved if is_valid_image_url(resolved, blacklist_keywords, strict_ext) else ""


def parse_srcset(srcset: str) -> list[str]:
    out: list[str] = []
    for part in srcset.split(","):
        token = part.strip().split(" ")[0].strip()
        if token:
            out.append(token)
    return out


def attrs_to_image_candidates(attrs: dict[str, str]) -> list[str]:
    candidates = []
    for key in ("src", "data-src", "data-original", "data-lazy-src"):
        value = attrs.get(key, "")
        if value:
            candidates.append(value)
    srcset = attrs.get("srcset") or attrs.get("data-srcset")
    if srcset:
        candidates.extend(parse_srcset(srcset))
    return candidates


def base_url_from_attrs(tag: str, attrs: dict[str, str], current: dict[str, str]) -> None:
    if tag == "meta":
        content = (attrs.get("content") or "").strip()
        property_name = (attrs.get("property") or "").lower()
        name = (attrs.get("name") or "").lower()
        if property_name == "og:url" and content and not current["og"]:
            current["og"] = content
        elif name == "twitter:url" and content and not current["twitter"]:
            current["twitter"] = content
    elif tag == "link":
        rel = (attrs.get("rel") or "").lower().split()
        href = (attrs.get("href") or "").strip()
        if "canonical" in rel and href and not current["canonical"]:
            current["canonical"] = href
    elif tag == "base" and not current["base"]:
        current["base"] = (attrs.get("href") or "").strip()


def effective_base_url(values: dict[str, str], fallback: str) -> str:
    return values["og"] or values["twitter"] or values["canonical"] or values["base"] or fallback


class ImageURLParser(HTMLParser):
    """Stream only the tags needed for image URL extraction."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.image_candidates: list[str] = []
        self.og_url = ""
        self.twitter_url = ""
        self.canonical_url = ""
        self.base_url = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attr_map = {key.lower(): (value or "").strip() for key, value in attrs}

        if tag == "img":
            for key in ("src", "data-src", "data-original", "data-lazy-src"):
                value = attr_map.get(key, "")
                if value:
                    self.image_candidates.append(value)

            srcset = attr_map.get("srcset") or attr_map.get("data-srcset")
            if srcset:
                self.image_candidates.extend(parse_srcset(srcset))
            return

        if tag == "meta":
            content = attr_map.get("content", "")
            if attr_map.get("property", "").lower() == "og:url" and content and not self.og_url:
                self.og_url = content
            elif attr_map.get("name", "").lower() == "twitter:url" and content and not self.twitter_url:
                self.twitter_url = content
            return

        if tag == "link":
            rel = attr_map.get("rel", "").lower().split()
            href = attr_map.get("href", "")
            if "canonical" in rel and href and not self.canonical_url:
                self.canonical_url = href
            return

        if tag == "base" and not self.base_url:
            self.base_url = attr_map.get("href", "")

    def effective_base_url(self, fallback: str) -> str:
        return self.og_url or self.twitter_url or self.canonical_url or self.base_url or fallback


def extract_image_urls(html: str, base_url: str, blacklist_keywords: tuple[str, ...], strict_ext: bool) -> list[str]:
    raw_candidates: list[str] = []
    base_values = {"og": "", "twitter": "", "canonical": "", "base": ""}

    if SelectolaxHTMLParser is not None:
        tree = SelectolaxHTMLParser(html)
        for node in tree.css("img"):
            raw_candidates.extend(attrs_to_image_candidates(dict(node.attributes)))
        for selector, tag in (("meta", "meta"), ("link", "link"), ("base", "base")):
            for node in tree.css(selector):
                base_url_from_attrs(tag, dict(node.attributes), base_values)
    elif lxml_html is not None:
        tree = lxml_html.fromstring(html)
        for node in tree.xpath("//img"):
            raw_candidates.extend(attrs_to_image_candidates(dict(node.attrib)))
        for tag in ("meta", "link", "base"):
            for node in tree.xpath(f"//{tag}"):
                base_url_from_attrs(tag, dict(node.attrib), base_values)
    else:
        parser = ImageURLParser()
        parser.feed(html)
        parser.close()
        raw_candidates = parser.image_candidates
        base_values = {
            "og": parser.og_url,
            "twitter": parser.twitter_url,
            "canonical": parser.canonical_url,
            "base": parser.base_url,
        }

    effective_base = effective_base_url(base_values, base_url)
    urls: set[str] = set()

    for raw in raw_candidates:
        resolved = resolve_and_validate_url(raw, effective_base, blacklist_keywords, strict_ext)
        if resolved:
            urls.add(resolved)

    return sorted(urls)


@lru_cache(maxsize=1_000_000)
def get_url_domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def process_one(
    html_path: Path,
    base_url: str,
    blacklist_keywords: tuple[str, ...],
    strict_image_ext: bool,
) -> TaskResult:
    try:
        html = html_path.read_text(encoding="utf-8", errors="ignore")
        image_urls = extract_image_urls(html, base_url, blacklist_keywords, strict_image_ext)
        domains = sorted({get_url_domain(u) for u in image_urls if get_url_domain(u)})

        return TaskResult(
            html_path=str(html_path),
            ok=True,
            image_count=len(image_urls),
            domains=domains,
            image_urls=image_urls,
        )
    except Exception as exc:
        return TaskResult(
            html_path=str(html_path),
            ok=False,
            image_count=0,
            domains=[],
            image_urls=[],
            error=f"{type(exc).__name__}: {exc}",
        )


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lightweight image scan for html file list.")
    parser.add_argument("--html-counts", default="outputs/final/htmls/2015/html_counts.json")
    parser.add_argument("--html-root", default="")
    parser.add_argument("--workers", type=int, default=64)
    parser.add_argument("--queue-factor", type=int, default=4)
    parser.add_argument("--base-url", default="")
    parser.add_argument("--image-blacklist", default="logo,icon,ads,banner,sprite,avatar")
    parser.add_argument("--strict-image-ext", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--report-prefix", default="outputs/final/image_scan")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    counts_path = Path(args.html_counts)
    if not counts_path.exists():
        raise SystemExit(f"html counts file not found: {counts_path}")
    if args.workers <= 0:
        raise SystemExit("--workers must be > 0")
    if args.queue_factor <= 0:
        raise SystemExit("--queue-factor must be > 0")

    blacklist_keywords = tuple(
        x.strip().lower() for x in args.image_blacklist.split(",") if x.strip()
    ) or DEFAULT_IMAGE_BLACKLIST

    counts = load_html_counts(counts_path)
    html_root = Path(args.html_root) if args.html_root else counts_path.parent.parent
    total = sum(counts.values())
    print(f"Total html paths: {total}")

    prefix = Path(args.report_prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)

    summary_path = prefix.with_name(prefix.name + "_summary.json")
    failures_path = prefix.with_name(prefix.name + "_failures.jsonl")
    records_path = prefix.with_name(prefix.name + "_records.jsonl")
    domain_urls_path = prefix.with_name(prefix.name + "_domain_urls.json")

    html_iter = iter_html_paths(counts_path, html_root)
    max_pending = args.workers * args.queue_factor

    ok_files = 0
    failed_files = 0
    html_with_images = 0
    html_without_images = 0
    total_images = 0

    domain_to_urls: dict[str, set[str]] = {}
    seen_image_urls: set[str] = set()
    duplicate_images = 0

    with (
        ProcessPoolExecutor(max_workers=args.workers) as ex,
        failures_path.open("w", encoding="utf-8") as fail_f,
        records_path.open("w", encoding="utf-8") as rec_f,
        tqdm(total=total, desc="Scanning HTML", unit="html", dynamic_ncols=True) as pbar,
    ):
        pending = set()

        def submit_more() -> None:
            try:
                while len(pending) < max_pending:
                    html_path = next(html_iter)
                    future = ex.submit(
                        process_one,
                        html_path,
                        args.base_url,
                        blacklist_keywords,
                        args.strict_image_ext,
                    )
                    pending.add(future)
            except StopIteration:
                pass

        submit_more()

        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for fu in done:
                r = fu.result()
                pbar.update(1)

                if not r.ok:
                    failed_files += 1
                    fail_f.write(json.dumps({
                        "html_path": r.html_path,
                        "error": r.error,
                    }, ensure_ascii=False) + "\n")
                    continue

                ok_files += 1
                unique_urls = []
                for image_url in r.image_urls:
                    if image_url in seen_image_urls:
                        duplicate_images += 1
                        continue
                    seen_image_urls.add(image_url)
                    unique_urls.append(image_url)

                unique_domains = sorted({
                    get_url_domain(url)
                    for url in unique_urls
                    if get_url_domain(url)
                })
                total_images += len(unique_urls)
                if unique_urls:
                    html_with_images += 1
                else:
                    html_without_images += 1

                rec_f.write(json.dumps({
                    "html_path": r.html_path,
                    "image_count": len(unique_urls),
                    "domains": unique_domains,
                    "image_urls": unique_urls,
                }, ensure_ascii=False) + "\n")

                for u in unique_urls:
                    d = get_url_domain(u)
                    if not d:
                        continue
                    domain_to_urls.setdefault(d, set()).add(u)

            submit_more()

    domain_urls_json = {d: sorted(urls) for d, urls in sorted(domain_to_urls.items())}
    write_json(domain_urls_path, domain_urls_json)

    summary = {
        "input_html_paths": total,
        "ok_files": ok_files,
        "failed_files": failed_files,
        "html_with_images": html_with_images,
        "html_without_images": html_without_images,
        "total_images": total_images,
        "duplicate_images": duplicate_images,
        "unique_image_urls": len(seen_image_urls),
        "unique_domains": len(domain_urls_json),
        "workers": args.workers,
        "queue_factor": args.queue_factor,
        "strict_image_ext": args.strict_image_ext,
    }
    write_json(summary_path, summary)

    print(f"Done. summary={summary_path}")
    print(f"Done. failures={failures_path}")
    print(f"Done. records={records_path}")
    print(f"Done. domain_urls={domain_urls_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
