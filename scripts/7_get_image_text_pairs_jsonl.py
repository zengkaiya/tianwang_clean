#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import re
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

from tqdm import tqdm


TEXT_NORMALIZE_RE = re.compile(r"\s+")
IMAGE_URL_ATTRS = [
    "src",
    "data-src",
    "data-original",
    "data-lazy-src",
    "data-ks-lazyload",
    "data-actualsrc",
    "srcset",
]


@dataclass
class HTMLNode:
    tag: str
    attrs: dict[str, str]
    parent: HTMLNode | None
    children: list[HTMLNode]
    text: str = ""


@dataclass
class ImageTag:
    url: str
    node: HTMLNode
    token_index: int


@dataclass
class StreamToken:
    typ: str
    data: str
    attrs: dict[str, str]
    stack: list[str]


VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


class ImageCaptionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = HTMLNode(tag="document", attrs={}, parent=None, children=[])
        self.stack: list[HTMLNode] = [self.root]
        self.tokens: list[StreamToken] = []
        self.base_href = ""
        self.images: list[ImageTag] = []

    @property
    def current(self) -> HTMLNode:
        return self.stack[-1]

    def _push_node(self, node: HTMLNode) -> None:
        self.current.children.append(node)
        if node.tag not in VOID_TAGS:
            self.stack.append(node)

    def _stack_tags(self) -> list[str]:
        return [node.tag for node in self.stack if node.tag != "document"]

    def _push_token(self, typ: str, data: str, attrs: dict[str, str], stack: list[str]) -> None:
        self.tokens.append(StreamToken(typ=typ, data=data, attrs=attrs, stack=stack))

    def _pop_to(self, tag: str) -> None:
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        attr_map = {k.lower(): (v or "") for k, v in attrs}

        if t == "base" and not self.base_href:
            href = attr_map.get("href", "").strip()
            if href:
                self.base_href = href
            return

        node = HTMLNode(tag=t, attrs=attr_map, parent=self.current, children=[])
        self._push_node(node)

        if t == "img":
            raw_url = pick_img_raw_url(attr_map)
            if not raw_url:
                return
            url = urljoin(self.base_href, raw_url) if self.base_href else raw_url
            url = normalize_url(url)
            token_stack = self._stack_tags() + ["img"]
            self._push_token("img", "", attr_map, token_stack)
            self.images.append(ImageTag(url=url, node=node, token_index=len(self.tokens) - 1))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        t = tag.lower()
        if t not in VOID_TAGS:
            self._pop_to(t)

    def handle_endtag(self, tag: str) -> None:
        self._pop_to(tag.lower())

    def handle_data(self, data: str) -> None:
        text = normalize_text(data)
        if not text:
            return
        self.current.children.append(HTMLNode(tag="#text", attrs={}, parent=self.current, children=[], text=text))
        self._push_token("text", text, {}, self._stack_tags())


def node_text(node: HTMLNode) -> str:
    if node.tag == "#text":
        return node.text
    parts: list[str] = []
    for child in node.children:
        text = node_text(child)
        if text:
            parts.append(text)
    return normalize_text(" ".join(parts))


def find_parent(node: HTMLNode, tag: str) -> HTMLNode | None:
    cur = node.parent
    while cur is not None:
        if cur.tag == tag:
            return cur
        cur = cur.parent
    return None


def find_first_descendant(node: HTMLNode, tag: str) -> HTMLNode | None:
    for child in node.children:
        if child.tag == tag:
            return child
        found = find_first_descendant(child, tag)
        if found is not None:
            return found
    return None


def common_prefix_len(a: list[str], b: list[str]) -> int:
    n = min(len(a), len(b))
    idx = 0
    while idx < n and a[idx] == b[idx]:
        idx += 1
    return idx


def find_near_text(tokens: list[StreamToken], img_idx: int, direction: int, max_steps: int = 40) -> tuple[str, int, int]:
    i = img_idx + direction
    steps = 0
    best_text = ""
    best_distance = 10**9
    best_depth = -1

    while 0 <= i < len(tokens) and steps < max_steps:
        tok = tokens[i]
        if tok.typ == "text" and len(tok.data) >= 2:
            depth = common_prefix_len(tokens[img_idx].stack, tok.stack)
            distance = abs(i - img_idx)
            if depth > best_depth or (depth == best_depth and distance < best_distance):
                best_text = tok.data
                best_distance = distance
                best_depth = depth
        i += direction
        steps += 1

    return best_text, best_distance, best_depth


def add_candidate(candidates: list[dict[str, str]], source: str, text: str) -> None:
    text = normalize_text(text)
    if not text:
        return
    for item in candidates:
        if item["source"] == source and item["text"] == text:
            return
    candidates.append({"source": source, "text": text})


def src_filename_caption(src: str) -> str:
    src = src.strip()
    if not src:
        return ""
    if "/" in src:
        filename = src.split("/")[-1].split("?", 1)[0].split("#", 1)[0]
    else:
        filename = src.split("?", 1)[0].split("#", 1)[0]
    if "." in filename:
        filename = filename.rsplit(".", 1)[0]
    filename = normalize_text(filename)
    if len(filename) <= 3 or filename.isdigit():
        return ""
    return filename


def extract_caption_candidates(img: HTMLNode) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []

    figure = find_parent(img, "figure")
    if figure is not None:
        figcap = find_first_descendant(figure, "figcaption")
        if figcap is not None:
            add_candidate(candidates, "figure.figcaption", node_text(figcap))

    parent = img.parent
    if parent is not None:
        idx = -1
        for i, child in enumerate(parent.children):
            if child is img:
                idx = i
                break

        if idx != -1:
            for j in range(idx - 1, -1, -1):
                sib = parent.children[j]
                if sib.tag == "#text":
                    add_candidate(candidates, "sibling.prev_text", sib.text)
                    break
                text = node_text(sib)
                if text:
                    add_candidate(candidates, f"sibling.prev_{sib.tag}", text)
                    break

            for j in range(idx + 1, len(parent.children)):
                sib = parent.children[j]
                if sib.tag == "#text":
                    add_candidate(candidates, "sibling.next_text", sib.text)
                    break
                text = node_text(sib)
                if text:
                    add_candidate(candidates, f"sibling.next_{sib.tag}", text)
                    break

        for child in parent.children:
            if child is img:
                continue
            if child.tag == "figcaption":
                add_candidate(candidates, "parent.figcaption", node_text(child))
                continue
            if child.tag not in {"div", "p", "span"}:
                continue
            class_text = (child.attrs.get("class", "") or "").lower()
            if any(key in class_text for key in ("caption", "desc", "info", "txt")):
                add_candidate(candidates, f"parent.{child.tag}.class", node_text(child))

    a_tag = find_parent(img, "a")
    if a_tag is not None:
        add_candidate(candidates, "a.title", a_tag.attrs.get("title", ""))

    add_candidate(candidates, "img.title", img.attrs.get("title", ""))
    add_candidate(candidates, "img.alt", img.attrs.get("alt", ""))

    return candidates


def extract_nearby_text_candidates(parser: ImageCaptionParser, img: ImageTag) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    prev_text, prev_dist, prev_depth = find_near_text(parser.tokens, img.token_index, direction=-1)
    next_text, next_dist, next_depth = find_near_text(parser.tokens, img.token_index, direction=1)

    if prev_text and (prev_depth >= 2 or prev_dist <= 8):
        add_candidate(candidates, "nearby_prev", prev_text)
    if next_text and (next_depth >= 2 or next_dist <= 8):
        add_candidate(candidates, "nearby_next", next_text)
    return candidates


def normalize_text(text: str) -> str:
    return TEXT_NORMALIZE_RE.sub(" ", text).strip()


def normalize_url(url: str) -> str:
    url = str(url).strip()
    if not url:
        return ""
    parsed = urlsplit(url)
    if parsed.scheme.lower() in {"http", "https"}:
        return urlunsplit(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                parsed.path,
                parsed.query,
                parsed.fragment,
            )
        )
    return url


def pick_img_raw_url(attrs: dict[str, str]) -> str:
    for key in IMAGE_URL_ATTRS:
        value = attrs.get(key, "").strip()
        if not value:
            continue
        if key == "srcset":
            first = value.split(",", 1)[0].strip()
            if first:
                value = first.split(" ", 1)[0].strip()
        if value:
            return value
    return ""


def read_text_best_effort(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8", "gb18030", "latin1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin1", errors="ignore")


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


def _load_accessible_images_chunk(lines: list[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
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

        path = str(row.get("path", row.get("local_path", ""))).strip()
        if "ok" in row and not row.get("ok", False):
            continue

        w = int(row.get("width", -1))
        h = int(row.get("height", -1))
        if w <= 0 or h <= 0 or min(w, h) <= 100:
            continue

        url = normalize_url(row.get("url", ""))
        if url:
            out[url] = {"width": w, "height": h, "path": path}
    return out


def load_accessible_images(path: Path, workers: int, chunk_size: int) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    chunks = iter_line_chunks(path, chunk_size)
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for part in tqdm(
            ex.map(_load_accessible_images_chunk, chunks, chunksize=1),
            desc="Filtering images",
            unit="chunk",
            dynamic_ncols=True,
        ):
            out.update(part)
    return out


_WANTED_URLS: set[str] = set()


def _init_html_job_worker(wanted_urls: set[str]) -> None:
    global _WANTED_URLS
    _WANTED_URLS = wanted_urls


def _filter_html_jobs_chunk(lines: list[str]) -> list[tuple[str, list[str]]]:
    jobs: list[tuple[str, list[str]]] = []
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

        html_path = str(row.get("html_path", "")).strip()
        urls = row.get("image_urls", [])
        if not html_path or not isinstance(urls, list):
            continue

        filtered_urls = [
            normalize_url(u)
            for u in urls
            if isinstance(u, str) and normalize_url(u) in _WANTED_URLS
        ]
        if filtered_urls:
            jobs.append((html_path, filtered_urls))
    return jobs


def load_html_jobs(path: Path, wanted_urls: set[str], workers: int, chunk_size: int) -> list[tuple[Path, list[str]]]:
    jobs: list[tuple[Path, list[str]]] = []
    chunks = iter_line_chunks(path, chunk_size)
    with ProcessPoolExecutor(
        max_workers=workers,
        initializer=_init_html_job_worker,
        initargs=(wanted_urls,),
    ) as ex:
        for part in tqdm(
            ex.map(_filter_html_jobs_chunk, chunks, chunksize=1),
            desc="Collecting html jobs",
            unit="chunk",
            dynamic_ncols=True,
        ):
            jobs.extend((Path(html_path), urls) for html_path, urls in part)
    return jobs


def merge_candidate_lists(existing: list[dict[str, str]], new_items: list[dict[str, str]]) -> list[dict[str, str]]:
    merged = list(existing)
    seen = {(item.get("source", ""), item.get("text", "")) for item in merged}
    for item in new_items:
        source = str(item.get("source", ""))
        text = normalize_text(str(item.get("text", "")))
        if not source or not text:
            continue
        key = (source, text)
        if key in seen:
            continue
        merged.append({"source": source, "text": text})
        seen.add(key)
    return merged


def is_nearby_candidate(item: dict[str, str]) -> bool:
    return str(item.get("source", "")).startswith("nearby_")


def select_caption(candidates: list[dict[str, str]]) -> tuple[str, str]:
    structural = [item for item in candidates if not is_nearby_candidate(item)]
    nearby = [item for item in candidates if is_nearby_candidate(item)]
    ordered = structural + nearby

    structural = sorted(structural, key=lambda item: len(normalize_text(str(item.get("text", "")))), reverse=True)
    nearby = sorted(nearby, key=lambda item: len(normalize_text(str(item.get("text", "")))), reverse=True)

    for item in structural:
        text = normalize_text(str(item.get("text", "")))
        if text:
            return text, str(item.get("source", ""))

    for item in nearby:
        text = normalize_text(str(item.get("text", "")))
        if text:
            return text, str(item.get("source", ""))

    for item in ordered:
        text = normalize_text(str(item.get("text", "")))
        if text:
            return text, str(item.get("source", ""))

    return "", ""


def parse_html_captions(html_path: Path, wanted_urls: set[str]) -> dict[str, dict[str, Any]]:
    try:
        html_text = read_text_best_effort(html_path)
        parser = ImageCaptionParser()
        parser.feed(html_text)
        parser.close()
    except Exception:
        return {}

    captions: dict[str, dict[str, Any]] = {}
    for img in parser.images:
        if img.url not in wanted_urls:
            continue
        candidates = extract_caption_candidates(img.node)
        candidates = merge_candidate_lists(candidates, extract_nearby_text_candidates(parser, img))
        selected_caption, selected_source = select_caption(candidates)
        current = captions.get(img.url)
        if current is None:
            captions[img.url] = {
                "caption": selected_caption,
                "caption_source": selected_source,
                "caption_candidates": candidates,
            }
        else:
            merged_candidates = merge_candidate_lists(current.get("caption_candidates", []), candidates)
            selected_caption, selected_source = select_caption(merged_candidates)
            captions[img.url] = {
                "caption": selected_caption,
                "caption_source": selected_source,
                "caption_candidates": merged_candidates,
            }
    return captions


def load_existing_urls(path: Path) -> set[str]:
    if not path.exists():
        return set()
    done: set[str] = set()
    with path.open("r", encoding="utf-8") as f:
        for line in f:
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
                done.add(url)
    return done


def load_existing_urls_from_paths(paths: list[Path]) -> set[str]:
    done: set[str] = set()
    for path in paths:
        done.update(load_existing_urls(path))
    return done


def append_jsonl_rows(handle, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Get image-text pairs from HTMLs.")
    parser.add_argument("--image-size-detailed", default="outputs/2013_2014/image_size_scan_detailed.jsonl")
    parser.add_argument("--image-scan-per-html", default="outputs/2013_2014/image_scan_per_html.jsonl")
    parser.add_argument("--output", default="outputs/2013_2014/image_text_pairs.jsonl")
    parser.add_argument("--workers", type=int, default=32)
    parser.add_argument("--load-workers", type=int, default=max(1, min(8, mp.cpu_count() or 4)))
    parser.add_argument("--load-chunk-size", type=int, default=50000, help="JSONL lines per loading process task")
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()

    image_size_path = Path(args.image_size_detailed)
    per_html_path = Path(args.image_scan_per_html)
    output_path = Path(args.output)
    no_caption_path = output_path.with_name(output_path.stem + "_nocapiton" + output_path.suffix)

    if args.workers <= 0:
        raise SystemExit("--workers must be > 0")
    if args.load_workers <= 0:
        raise SystemExit("--load-workers must be > 0")
    if args.load_chunk_size <= 0:
        raise SystemExit("--load-chunk-size must be > 0")
    if not image_size_path.exists():
        raise SystemExit(f"image size file not found: {image_size_path}")
    if not per_html_path.exists():
        raise SystemExit(f"image per html file not found: {per_html_path}")

    if not args.resume:
        for path in (output_path, no_caption_path):
            if path.exists():
                path.unlink()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    url2size = load_accessible_images(
        image_size_path,
        workers=args.load_workers,
        chunk_size=args.load_chunk_size,
    )
    wanted_urls = set(url2size.keys())
    print(f"Accessible image urls: {len(url2size)}")

    html_jobs = load_html_jobs(
        per_html_path,
        wanted_urls=wanted_urls,
        workers=args.load_workers,
        chunk_size=args.load_chunk_size,
    )

    print(f"Htmls with target urls: {len(html_jobs)}")

    done_urls = (
        load_existing_urls_from_paths([output_path, no_caption_path])
        if args.resume
        else set()
    )
    if done_urls:
        print(f"Already done urls (resume): {len(done_urls)}")

    total_rows = sum(len(urls) for _, urls in html_jobs)
    written = 0
    no_caption_written = 0

    with (
        output_path.open("a", encoding="utf-8") as out_f,
        no_caption_path.open("a", encoding="utf-8") as no_caption_f,
        ThreadPoolExecutor(max_workers=args.workers) as ex,
    ):
        future_urls = {
            ex.submit(parse_html_captions, html_path, set(urls)): urls
            for html_path, urls in html_jobs
            if any(u not in done_urls for u in urls)
        }

        for fu in tqdm(as_completed(future_urls), total=len(future_urls), desc="Extracting captions", unit="html", dynamic_ncols=True):
            captions = fu.result()
            rows: list[dict[str, Any]] = []
            no_caption_rows: list[dict[str, Any]] = []
            for url in future_urls[fu]:
                if url in done_urls:
                    continue
                size = url2size.get(url)
                if not size:
                    continue
                caption = captions.get(
                    url,
                    {
                        "caption": "",
                        "caption_source": "",
                        "caption_candidates": [],
                    },
                )
                row = {
                    "url": url,
                    "caption": caption.get("caption", ""),
                    "caption_source": caption.get("caption_source", ""),
                    "caption_candidates": caption.get("caption_candidates", []),
                    "path": size.get("path", ""),
                    "width": size["width"],
                    "height": size["height"],
                }
                if str(row["caption"]).strip():
                    rows.append(row)
                else:
                    no_caption_rows.append(row)
                done_urls.add(url)

            if rows:
                append_jsonl_rows(out_f, rows)
                written += len(rows)
            if no_caption_rows:
                append_jsonl_rows(no_caption_f, no_caption_rows)
                no_caption_written += len(no_caption_rows)

    print(f"Done. written={written}, no_caption={no_caption_written}, candidate_pairs={total_rows}")
    print(f"Output: {output_path}")
    print(f"No-caption output: {no_caption_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
