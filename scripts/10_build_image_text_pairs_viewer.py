#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


HTML_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Image Text Pairs Viewer</title>
  <style>
    :root {
      --bg: #0f172a;
      --panel: rgba(15, 23, 42, 0.78);
      --panel-2: rgba(30, 41, 59, 0.85);
      --card: rgba(255, 255, 255, 0.06);
      --card-border: rgba(148, 163, 184, 0.18);
      --text: #e2e8f0;
      --muted: #94a3b8;
      --accent: #38bdf8;
      --accent-2: #f59e0b;
      --good: #34d399;
      --shadow: 0 18px 60px rgba(0, 0, 0, 0.35);
      --radius: 18px;
    }
    * { box-sizing: border-box; }
    html, body { height: 100%; }
    body {
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(56, 189, 248, 0.16), transparent 25%),
        radial-gradient(circle at top right, rgba(245, 158, 11, 0.12), transparent 24%),
        linear-gradient(180deg, #020617 0%, #0f172a 40%, #111827 100%);
    }
    a { color: var(--accent); text-decoration: none; }
    a:hover { text-decoration: underline; }
    .shell { max-width: 1600px; margin: 0 auto; padding: 20px; }
    .hero {
      position: sticky; top: 0; z-index: 20;
      backdrop-filter: blur(18px);
      background: linear-gradient(180deg, rgba(2, 6, 23, 0.98), rgba(15, 23, 42, 0.72));
      border: 1px solid rgba(148, 163, 184, 0.16);
      border-radius: calc(var(--radius) + 4px);
      box-shadow: var(--shadow);
      padding: 16px; margin-bottom: 18px;
    }
    .title-row { display: flex; gap: 12px; align-items: center; justify-content: space-between; flex-wrap: wrap; }
    .title { font-size: 22px; font-weight: 750; letter-spacing: 0.2px; margin: 0; }
    .subtitle { color: var(--muted); font-size: 13px; margin-top: 6px; }
    .status { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-top: 14px; }
    .pill {
      display: inline-flex; align-items: center; gap: 8px;
      padding: 9px 12px; border-radius: 999px;
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid rgba(148, 163, 184, 0.16);
      color: var(--text); font-size: 13px; white-space: nowrap;
    }
    .pill strong { color: white; }
    .controls {
      display: grid;
      grid-template-columns: 1.3fr 0.7fr 0.6fr 0.6fr;
      gap: 10px;
      margin-top: 14px;
    }
    .controls input, .controls select, .controls button {
      width: 100%; border-radius: 12px; border: 1px solid rgba(148, 163, 184, 0.18);
      background: rgba(15, 23, 42, 0.9); color: var(--text);
      padding: 11px 12px; outline: none; font-size: 14px;
    }
    .controls input::placeholder { color: #64748b; }
    .controls button {
      cursor: pointer;
      background: linear-gradient(180deg, rgba(56, 189, 248, 0.26), rgba(56, 189, 248, 0.14));
      font-weight: 650;
    }
    .controls button:hover { border-color: rgba(56, 189, 248, 0.45); }
    .tip { margin-top: 10px; font-size: 12px; color: var(--muted); line-height: 1.5; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 14px; align-items: start; }
    .card {
      background: linear-gradient(180deg, rgba(30, 41, 59, 0.72), rgba(15, 23, 42, 0.84));
      border: 1px solid var(--card-border);
      border-radius: var(--radius);
      overflow: hidden;
      box-shadow: var(--shadow);
      display: flex;
      flex-direction: column;
      min-height: 280px;
    }
    .img-wrap {
      aspect-ratio: 4 / 3;
      background:
        radial-gradient(circle at center, rgba(255,255,255,0.08), transparent 55%),
        rgba(2, 6, 23, 0.7);
      display: grid;
      place-items: center;
      overflow: hidden;
      border-bottom: 1px solid rgba(148, 163, 184, 0.16);
    }
    .img-wrap img {
      width: 100%; height: 100%; object-fit: contain; display: block;
      background: rgba(2, 6, 23, 0.15);
    }
    .meta { padding: 12px 12px 14px; display: grid; gap: 10px; }
    .url { font-size: 12px; color: var(--muted); word-break: break-all; line-height: 1.45; }
    .caption { font-size: 14px; line-height: 1.55; color: #f8fafc; min-height: 22px; }
    .caption.empty { color: #64748b; font-style: italic; }
    details { border-top: 1px dashed rgba(148, 163, 184, 0.16); padding-top: 8px; }
    summary { cursor: pointer; color: var(--accent); font-size: 13px; user-select: none; }
    .candidates { margin: 8px 0 0; padding: 0; list-style: none; display: grid; gap: 8px; }
    .candidate {
      padding: 9px 10px;
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(148, 163, 184, 0.12);
      font-size: 13px;
      line-height: 1.45;
      word-break: break-word;
    }
    .candidate .source {
      display: inline-block; margin-bottom: 6px; font-size: 11px; color: #fde68a;
      background: rgba(245, 158, 11, 0.12);
      border: 1px solid rgba(245, 158, 11, 0.25);
      padding: 2px 7px; border-radius: 999px;
    }
    .empty-state {
      padding: 30px; border-radius: var(--radius);
      border: 1px dashed rgba(148, 163, 184, 0.28);
      background: rgba(15, 23, 42, 0.65);
      color: var(--muted); text-align: center;
    }
    .hidden { display: none !important; }
    .footer { margin: 18px 0 6px; color: var(--muted); font-size: 12px; text-align: center; }
    @media (max-width: 900px) { .controls { grid-template-columns: 1fr 1fr; } }
    @media (max-width: 560px) {
      .shell { padding: 12px; }
      .controls { grid-template-columns: 1fr; }
      .grid { grid-template-columns: 1fr; }
      .title { font-size: 18px; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <div class="hero">
      <div class="title-row">
        <div>
          <h1 class="title">Image Text Pairs Viewer</h1>
          <div class="subtitle">数据已直接写入 HTML 内部，离线打开即可查看图文对结果。</div>
        </div>
        <div class="pill">状态：<strong id="load-status">已内嵌</strong></div>
      </div>

      <div class="status">
        <div class="pill">总数 <strong id="total-count">0</strong></div>
        <div class="pill">当前显示 <strong id="shown-count">0</strong></div>
        <div class="pill">有候选 <strong id="candidate-count">0</strong></div>
        <div class="pill">有 caption <strong id="caption-count">0</strong></div>
      </div>

      <div class="controls">
        <input id="search" type="text" placeholder="搜索 caption / url / 候选文本" />
        <select id="candidate-filter">
          <option value="all">全部候选</option>
          <option value="with">只看有候选</option>
          <option value="empty">只看无候选</option>
        </select>
        <select id="caption-filter">
          <option value="all">全部 caption</option>
          <option value="with">只看有 caption</option>
          <option value="empty">只看空 caption</option>
        </select>
        <button id="reload">重新渲染</button>
      </div>

      <div class="tip">点击候选列可展开查看，图片默认懒加载。</div>
    </div>

    <div id="empty-state" class="empty-state hidden">正在加载数据。</div>
    <div id="grid" class="grid"></div>
    <div class="footer">每条记录展示一张图片，下方是 caption，再下方是 candidate 列。</div>
  </div>

  <script id="embedded-data" type="application/json">{{DATA_JSON}}</script>
  <script>
    const state = { rows: [], filtered: [] };
    const el = (id) => document.getElementById(id);

    function setStatus(text) { el('load-status').textContent = text; }
    function normalizeText(v) { return String(v || '').replace(/\s+/g, ' ').trim(); }
    function parseJson(text) {
      try { return JSON.parse(text); } catch (err) { return []; }
    }
    function renderStats(rows, filtered) {
      el('total-count').textContent = rows.length;
      el('shown-count').textContent = filtered.length;
      el('candidate-count').textContent = rows.filter((r) => Array.isArray(r.caption_candidates) && r.caption_candidates.length > 0).length;
      el('caption-count').textContent = rows.filter((r) => normalizeText(r.caption).length > 0).length;
    }
    function makeCandidateItem(item) {
      const li = document.createElement('li');
      li.className = 'candidate';
      const source = document.createElement('div');
      source.className = 'source';
      source.textContent = item.source || 'unknown';
      const text = document.createElement('div');
      text.textContent = item.text || '';
      li.appendChild(source);
      li.appendChild(text);
      return li;
    }
    function render(rows) {
      const search = normalizeText(el('search').value).toLowerCase();
      const candidateFilter = el('candidate-filter').value;
      const captionFilter = el('caption-filter').value;
      const filtered = rows.filter((row) => {
        const caption = normalizeText(row.caption);
        const candidates = Array.isArray(row.caption_candidates) ? row.caption_candidates : [];
        const blob = [row.url || '', caption, ...candidates.map((x) => `${x.source || ''} ${x.text || ''}`)].join(' ').toLowerCase();
        if (search && !blob.includes(search)) return false;
        if (candidateFilter === 'with' && candidates.length === 0) return false;
        if (candidateFilter === 'empty' && candidates.length > 0) return false;
        if (captionFilter === 'with' && !caption) return false;
        if (captionFilter === 'empty' && caption) return false;
        return true;
      });
      state.filtered = filtered;
      renderStats(rows, filtered);
      const grid = el('grid');
      grid.innerHTML = '';
      if (filtered.length === 0) {
        el('empty-state').classList.remove('hidden');
        grid.classList.add('hidden');
        el('empty-state').textContent = rows.length ? '没有匹配当前筛选条件的结果。' : '暂无数据。';
        return;
      }
      el('empty-state').classList.add('hidden');
      grid.classList.remove('hidden');
      const frag = document.createDocumentFragment();
      for (const row of filtered) {
        const card = document.createElement('article');
        card.className = 'card';
        const imgWrap = document.createElement('div');
        imgWrap.className = 'img-wrap';
        const img = document.createElement('img');
        img.loading = 'lazy';
        img.referrerPolicy = 'no-referrer';
        img.alt = row.caption || row.url || '';
        img.src = row.url || '';
        img.onerror = () => { imgWrap.innerHTML = '<div style="color:#94a3b8;font-size:13px;padding:20px;text-align:center;">图片加载失败</div>'; };
        imgWrap.appendChild(img);
        const meta = document.createElement('div');
        meta.className = 'meta';
        const url = document.createElement('div');
        url.className = 'url';
        url.textContent = row.url || '';
        const caption = document.createElement('div');
        const captionText = normalizeText(row.caption);
        caption.className = 'caption' + (captionText ? '' : ' empty');
        caption.textContent = captionText || '空 caption';
        const details = document.createElement('details');
        const summary = document.createElement('summary');
        summary.textContent = `候选列 (${Array.isArray(row.caption_candidates) ? row.caption_candidates.length : 0})`;
        const ul = document.createElement('ul');
        ul.className = 'candidates';
        const candidates = Array.isArray(row.caption_candidates) ? row.caption_candidates : [];
        for (const item of candidates) ul.appendChild(makeCandidateItem(item));
        details.appendChild(summary);
        details.appendChild(ul);
        meta.appendChild(url);
        meta.appendChild(caption);
        meta.appendChild(details);
        card.appendChild(imgWrap);
        card.appendChild(meta);
        frag.appendChild(card);
      }
      grid.appendChild(frag);
    }
    const DATA = parseJson(el('embedded-data').textContent || '[]');
    state.rows = Array.isArray(DATA) ? DATA : [];
    setStatus('已内嵌');
    render(state.rows);
    el('reload').addEventListener('click', () => render(state.rows));
    el('search').addEventListener('input', () => render(state.rows));
    el('candidate-filter').addEventListener('change', () => render(state.rows));
    el('caption-filter').addEventListener('change', () => render(state.rows));
  </script>
</body>
</html>
"""


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a self-contained HTML viewer for image-text pairs.")
    parser.add_argument("--input", default="outputs/2013_2014/image_text_pairs.jsonl")
    parser.add_argument("--output", default="image_text_pairs_viewer.html")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.exists():
        raise SystemExit(f"input not found: {input_path}")

    rows = read_jsonl(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data_json = json.dumps(rows, ensure_ascii=False)
    data_json = data_json.replace("</", "<\\/")
    html = HTML_TEMPLATE.replace("{{DATA_JSON}}", data_json)
    output_path.write_text(html, encoding="utf-8")
    print(f"Wrote {output_path} with {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
