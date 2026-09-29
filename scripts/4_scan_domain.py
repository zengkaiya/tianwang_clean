#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from tqdm import tqdm


@dataclass
class ProbeResult:
    target: str
    ok: bool
    status_code: int
    reason: str


@dataclass
class DomainCheckResult:
    domain: str
    count: int
    accessible: bool
    success_target: str
    success_status_code: int
    total_probes: int
    failed_probes: int
    probe_details: list[dict[str, Any]]


def load_domain_urls(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"invalid json format, expected object: {path}")
    return data


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def probe_url(url: str, timeout: float, user_agent: str) -> ProbeResult:
    req = Request(url, headers={"User-Agent": user_agent}, method="HEAD")
    try:
        with urlopen(req, timeout=timeout) as resp:
            code = int(getattr(resp, "status", 200))
            return ProbeResult(target=url, ok=(200 <= code < 400), status_code=code, reason="")
    except HTTPError as exc:
        code = int(exc.code)
        if code in (401, 403, 405):
            return ProbeResult(target=url, ok=True, status_code=code, reason="")
        return ProbeResult(target=url, ok=False, status_code=code, reason=f"HTTPError:{code}")
    except URLError as exc:
        return ProbeResult(target=url, ok=False, status_code=-1, reason=f"URLError:{exc.reason}")
    except socket.timeout:
        return ProbeResult(target=url, ok=False, status_code=-1, reason="timeout")
    except Exception as exc:  # pylint: disable=broad-except
        return ProbeResult(target=url, ok=False, status_code=-1, reason=f"{type(exc).__name__}:{exc}")


def normalize_prefix(path: str) -> str:
    p = (path or "").strip()
    if not p or p == "/":
        return "/"
    if not p.startswith("/"):
        p = "/" + p
    if not p.endswith("/"):
        p = p + "/"
    return p


def extract_prefixes_and_samples(urls: list[str], max_prefixes: int, max_samples: int) -> tuple[list[str], list[str]]:
    prefix_counter: dict[str, int] = {}
    samples: list[str] = []

    for u in urls:
        if len(samples) < max_samples:
            samples.append(u)
        parsed = urlparse(u)
        segs = [x for x in parsed.path.split("/") if x]
        if not segs:
            continue
        # 一级前缀：/bigpic/
        p1 = normalize_prefix("/" + segs[0])
        prefix_counter[p1] = prefix_counter.get(p1, 0) + 1
        # 二级前缀：/bigpic/20101202/ （可选）
        if len(segs) >= 2:
            p2 = normalize_prefix("/" + segs[0] + "/" + segs[1])
            prefix_counter[p2] = prefix_counter.get(p2, 0) + 1

    prefixes: list[str] = []
    if max_prefixes > 0:
        prefixes = ["/"]
        sorted_prefixes = sorted(prefix_counter.items(), key=lambda x: x[1], reverse=True)
        for p, _ in sorted_prefixes:
            if p not in prefixes:
                prefixes.append(p)
            if len(prefixes) >= max_prefixes:
                break
    return prefixes, samples


def build_probe_targets(domain: str, urls: list[str], max_prefixes: int, max_samples: int) -> list[str]:
    d = domain.strip().lower()
    if not d or d == "__no_domain__":
        return []

    prefixes, samples = extract_prefixes_and_samples(urls, max_prefixes=max_prefixes, max_samples=max_samples)

    targets: list[str] = []
    if max_prefixes == 0 and max_samples == 0:
        # 基础版：只探测根域名
        targets = [f"https://{d}/", f"http://{d}/"]
        return targets

    # 1) 域名根路径 + 前缀路径
    for scheme in ("https", "http"):
        for p in prefixes:
            if p == "/":
                targets.append(f"{scheme}://{d}/")
            else:
                targets.append(f"{scheme}://{d}{p}")
    # 2) 真实样本URL（优先原样 http/https）
    for s in samples:
        targets.append(s)

    # 去重保序
    deduped: list[str] = []
    seen: set[str] = set()
    for t in targets:
        if t not in seen:
            deduped.append(t)
            seen.add(t)
    return deduped


def check_domain(
    domain: str,
    count: int,
    urls: list[str],
    timeout: float,
    user_agent: str,
    max_prefixes: int,
    max_samples: int,
) -> DomainCheckResult:
    targets = build_probe_targets(domain, urls, max_prefixes=max_prefixes, max_samples=max_samples)
    if not targets:
        return DomainCheckResult(
            domain=domain,
            count=count,
            accessible=False,
            success_target="",
            success_status_code=-1,
            total_probes=0,
            failed_probes=0,
            probe_details=[],
        )

    details: list[dict[str, Any]] = []
    success_target = ""
    success_status_code = -1
    failed_probes = 0

    for t in targets:
        r = probe_url(t, timeout=timeout, user_agent=user_agent)
        details.append(
            {
                "target": r.target,
                "ok": r.ok,
                "status_code": r.status_code,
                "reason": r.reason,
            }
        )
        if r.ok:
            success_target = r.target
            success_status_code = r.status_code
            break
        failed_probes += 1

    accessible = bool(success_target)
    return DomainCheckResult(
        domain=domain,
        count=count,
        accessible=accessible,
        success_target=success_target,
        success_status_code=success_status_code,
        total_probes=len(details),
        failed_probes=failed_probes,
        probe_details=details,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parallel scan domains with path-prefix probing.")
    parser.add_argument(
        "--input",
        default="outputs/2013_2014/image_scan_domain_urls.json",
        help="domain->urls json from scan_image.py",
    )
    parser.add_argument("--output-prefix", default="outputs/2013_2014/domain_scan", help="output prefix")
    parser.add_argument("--workers", type=int, default=64, help="parallel workers")
    parser.add_argument("--timeout", type=float, default=5.0, help="per request timeout seconds")
    parser.add_argument("--max-prefixes", type=int, default=6, help="max inferred path prefixes per domain (including /); set 0 to disable prefixes")
    parser.add_argument("--max-samples", type=int, default=3, help="max sample urls per domain; set 0 to disable samples")
    parser.add_argument("--user-agent", default="Mozilla/5.0 (compatible; TianWangDomainScanner/2.0)", help="http user agent")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"input not found: {input_path}")
    if args.workers <= 0:
        raise SystemExit("--workers must be > 0")
    if args.timeout <= 0:
        raise SystemExit("--timeout must be > 0")
    if args.max_prefixes < 0:
        raise SystemExit("--max-prefixes must be >= 0")
    if args.max_samples < 0:
        raise SystemExit("--max-samples must be >= 0")

    domain_urls = load_domain_urls(input_path)
    items: list[tuple[str, int, list[str]]] = []
    for domain, payload in domain_urls.items():
        if isinstance(payload, list):
            # Current scan_image output: {"domain": [url, ...]}
            urls = [str(u) for u in payload]
            count = len(urls)
        elif isinstance(payload, dict):
            # Backward-compatible format: {"url_count": N, "urls": [...]}
            raw_urls = payload.get("urls", [])
            urls = [str(u) for u in raw_urls] if isinstance(raw_urls, list) else []
            count = int(payload.get("url_count", len(urls)))
        else:
            continue
        items.append((str(domain), count, urls))
    items.sort(key=lambda x: x[1], reverse=True)
    print(f"Loaded domains: {len(items)}")

    results: list[DomainCheckResult] = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = [
            ex.submit(
                check_domain,
                domain,
                count,
                urls,
                args.timeout,
                args.user_agent,
                args.max_prefixes,
                args.max_samples,
            )
            for domain, count, urls in items
        ]
        for fu in tqdm(as_completed(futures), total=len(futures), desc="Scanning domains", unit="domain", dynamic_ncols=True):
            results.append(fu.result())

    accessible = [r for r in results if r.accessible]
    inaccessible = [r for r in results if not r.accessible]

    accessible_domains = sorted([r.domain for r in accessible])
    accessible_domain_counts = {r.domain: r.count for r in sorted(accessible, key=lambda x: x.count, reverse=True)}

    detailed_rows = [
        {
            "domain": r.domain,
            "count": r.count,
            "accessible": r.accessible,
            "success_target": r.success_target,
            "success_status_code": r.success_status_code,
            "total_probes": r.total_probes,
            "failed_probes": r.failed_probes,
            "probe_details": r.probe_details,
        }
        for r in sorted(results, key=lambda x: x.count, reverse=True)
    ]

    total_domains = len(results)
    total_images = sum(r.count for r in results)
    accessible_images = sum(r.count for r in accessible)
    summary = {
        "total_domains": total_domains,
        "accessible_domains": len(accessible),
        "inaccessible_domains": len(inaccessible),
        "accessible_domain_ratio": (len(accessible) / total_domains * 100) if total_domains else 0.0,
        "total_images": total_images,
        "accessible_images": accessible_images,
        "accessible_image_ratio": (accessible_images / total_images * 100) if total_images else 0.0,
        "scan_policy": {
            "max_prefixes": args.max_prefixes,
            "max_samples": args.max_samples,
            "probe_order": "https/http root+prefixes then sample image urls; when max-prefixes=0 and max-samples=0, root-only",
        },
    }

    prefix = Path(args.output_prefix)
    write_json(prefix.with_name(prefix.name + "_accessible_domains.json"), accessible_domains)
    write_json(prefix.with_name(prefix.name + "_accessible_domain_counts.json"), accessible_domain_counts)
    write_json(prefix.with_name(prefix.name + "_detailed.json"), detailed_rows)
    write_json(prefix.with_name(prefix.name + "_summary.json"), summary)

    print(
        "Done. "
        f"accessible_domains={summary['accessible_domains']}/{summary['total_domains']} "
        f"({summary['accessible_domain_ratio']:.2f}%), "
        f"accessible_images={summary['accessible_images']}/{summary['total_images']} "
        f"({summary['accessible_image_ratio']:.2f}%)"
    )
    print(f"Outputs prefix: {prefix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
