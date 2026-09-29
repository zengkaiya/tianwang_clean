# TianWang 图文数据处理

本项目用于从 PKU TianWang 网页归档中提取图文对，并进一步执行图片、文本和安全性过滤。整体分为两个模块：

1. `scripts/`：下载 TianWang 原始包，解析 HTML，下载图片并生成原始图文对。
2. `danqing/`：对图文对进行更严格的图片质量、文本质量和 NSFW 过滤。

完整命令顺序见 [`pipeline.txt`](pipeline.txt)。所有命令默认在项目根目录执行。

## 目录结构

```text
scripts/                    原始图文对提取流水线
danqing/                    深度过滤流水线
danqing/danqing.sh          深度过滤入口
data/                       下载的原始包及仓库文件索引
outputs/final/htmls/        解析出的 HTML
outputs/final/images/       下载的图片
outputs/final/pairs/        图文对 JSONL
outputs/final/danqing/      深度过滤结果
pipeline.txt                完整执行命令
```

`data/`、`outputs/` 和模型文件不提交到 Git。

## 环境准备

主要依赖包括 Python 3、Hugging Face CLI、PyTorch、MXNet、Pillow、OpenCV、OpenCC、jieba、PaddleHub 和 tqdm。Danqing 模块的完整环境记录在：

```bash
uv venv --python 3.10
source .venv/bin/activate

uv pip install \
  torch==2.4.0+cu124 \
  torchvision==0.19.0+cu124 \
  torchaudio==2.4.0+cu124 \
  --index-url https://download.pytorch.org/whl/cu124

uv pip install -r danqing/requirements.txt
```

下载数据需要 Hugging Face Token，并要求 `hf` 命令可用：

```bash
export HF_TOKEN="your_huggingface_token"
```

## 模块一：生成原始图文对

### 1. 准备仓库文件索引

下载脚本需要以下三个仓库的文件列表：

```text
data/PKU_TianWang/repo_file_list.cache.txt
data/PKU_TianWang2/repo_file_list.cache.txt
data/PKU_TianWang3/repo_file_list.cache.txt
```

首次使用时可生成这些索引：(默认已提供)

```bash
python3 - <<'PY'
import os
from pathlib import Path
from huggingface_hub import HfApi

repos = [
    "OpenDCAI/PKU_TianWang",
    "OpenDCAI/PKU_TianWang2",
    "OpenDCAI/PKU_TianWang3",
]

api = HfApi(token=os.environ["HF_TOKEN"])
for repo_id in repos:
    output = Path("data") / repo_id.rsplit("/", 1)[-1] / "repo_file_list.cache.txt"
    output.parent.mkdir(parents=True, exist_ok=True)
    files = api.list_repo_files(repo_id=repo_id, repo_type="dataset")
    output.write_text("\n".join(files) + "\n", encoding="utf-8")
    print(f"{repo_id}: {len(files)} files -> {output}")
PY
```

### 2. 下载指定年份的数据

下面以 2015 年为例，`all` 表示下载该年份全部包：

```bash
./scripts/1_download_hf_files_year.sh 2015 16 \
  --max-parallel 16
```

也可以将 `all` 改为包数量，并通过 `--seed` 固定随机采样结果。下载结果和包列表写入：

```text
data/2015/
data/2015/selected_packages.tsv
```

使用 `--dry-run` 可以只生成选择列表而不下载。

### 3. 解析 HTML

```bash
bash scripts/2_read_tw_data_batch_simple.sh \
  data/2015/selected_packages.tsv \
  all \
  --jobs 128
```

该步骤使用 `scripts/2_export_htmls_from_packages.py` 作为内部导出器，输出：

```text
outputs/final/htmls/2015/
outputs/final/htmls/2015/html_counts.json
```

### 4. 提取图片 URL

```bash
python scripts/3_get_image_urls.py \
  --html-counts outputs/final/htmls/2015/html_counts.json \
  --html-root outputs/final/htmls \
  --workers 128 \
  --report-prefix outputs/final/analysis/2015/image_scan
```

主要输出：

```text
outputs/final/analysis/2015/image_scan_records.jsonl
outputs/final/analysis/2015/image_scan_domain_urls.json
```

### 5. 扫描可访问域名

```bash
python scripts/4_scan_domain.py \
  --input outputs/final/analysis/2015/image_scan_domain_urls.json \
  --output-prefix outputs/final/analysis/2015/domain_scan \
  --workers 128 \
  --timeout 5 \
  --max-prefixes 6 \
  --max-samples 3
```

后续下载使用生成的 `domain_scan_accessible_domains.json`。

### 6. 下载图片

图片下载支持并行、断点续跑和分片。下面运行第 4 个分片，共 4 个分片：

```bash
python scripts/5_scan_and_download_images.py \
  --accessible-domains outputs/final/analysis/2015/domain_scan_accessible_domains.json \
  --domain-urls outputs/final/analysis/2015/image_scan_domain_urls.json \
  --output-prefix outputs/final/images/2015/image_scan_4_4 \
  --output-root outputs/final/images/2015 \
  --workers 64 \
  --splits 4 \
  --index 4 \
  --resume
```

下载全部数据时，应分别运行 `--index 1` 至 `--index 4`。不同进程应使用不同的 `--output-prefix`。

### 7. 合并并分析图片结果

```bash
python scripts/6_analyze_image_size_scan.py \
  --input-dir outputs/final/images/2015 \
  --output-prefix outputs/final/analysis/2015/analyze_image_size_final \
  --merge-workers 16 \
  --workers 64 \
  --chunk-size 50000 \
  --topk 50
```

各下载分片会被合并为：

```text
outputs/final/images/2015/merged_success.jsonl
```

### 8. 生成原始图文对

```bash
python scripts/7_get_image_text_pairs_jsonl.py \
  --image-size-detailed outputs/final/images/2015/merged_success.jsonl \
  --image-scan-per-html outputs/final/analysis/2015/image_scan_records.jsonl \
  --output outputs/final/pairs/2015/image_text_pairs.jsonl \
  --workers 64 \
  --load-workers 16 \
  --load-chunk-size 50000 \
  --resume
```

每条 JSONL 记录主要包含图片 URL、本地路径、宽高、caption、caption 来源及候选 caption。无 caption 的记录会单独写入 `*_nocapiton.jsonl`。

### 9. 可选：CLIP 相似度过滤

原始图文对可在 Chinese-CLIP 项目中计算图文相似度。得到包含相似度字段的 JSONL 后，可在本项目中统计并按阈值过滤：

```bash
python scripts/9_analyze_caption_similarity_jsonl.py \
  --input outputs/final/pairs/2015/image_text_pairs_with_caption_similarity.jsonl \
  --output-sorted outputs/final/pairs/2015/image_text_pairs_with_caption_similarity_sorted.jsonl \
  --output-stats outputs/final/analysis/2015/caption_similarity_stats.json \
  --workers 64 \
  --chunk-size 50000

python scripts/9_filter_caption_similarity_jsonl.py \
  --input outputs/final/pairs/2015/image_text_pairs_with_caption_similarity_sorted.jsonl \
  --threshold 0.49 \
  --output outputs/final/pairs/2015/image_text_pairs_similarity_ge_0.49.jsonl
```

`danqing/danqing.sh` 默认读取最后生成的阈值过滤结果。

## 模块二：Danqing 深度过滤

Danqing 接收模块一生成的图文对 JSONL，并依次执行：

1. 图片尺寸和长宽比过滤。
2. 过滤 caption 中不含名词的样本。
3. 繁体转简体，并将文本 token 写入 RecordIO。
4. 去除无用词汇，按文本长度和信息熵过滤。
5. 过滤纯色、模糊和低信息熵图片。
6. 图片 NSFW、文本 NSFW 和敏感词过滤。
7. 过滤 UNK 过多或中文占比较低的文本，并移除剩余 UNK。

CN-CLIP tokenizer 所需代码和词表已内置在 `danqing/cn_clip_tokenizer/`，不依赖外部 `cn-clip-ctp` 目录。

### 配置输入输出

编辑 `danqing/danqing.sh` 顶部的版本名和第一步输入：

```bash
dataset="2015_v3"
export DANQING_OUTPUT_DIR="outputs/final/danqing/$dataset"
```

第一步默认输入：

```text
outputs/final/pairs/2015/image_text_pairs_similarity_ge_0.49.jsonl
```

如果不执行 CLIP 相似度过滤，可以将 `--input` 改为模块一直接生成的 `image_text_pairs.jsonl`。

### 执行过滤

```bash
bash danqing/danqing.sh
```

各阶段通过 `DANQING_OUTPUT_DIR` 读取上一步结果并写入下一步结果。最终文件为：

```text
outputs/final/danqing/2015_v3/final.idx
outputs/final/danqing/2015_v3/final.rec
```

可将最终 RecordIO 解码为便于检查的图片和 JSONL：

```bash
python scripts/11_decode_final_recordio.py \
  --input-prefix outputs/final/danqing/2015_v3/final \
  --output-dir outputs/final/danqing/2015_v3/final_decoded
```

## 并行与断点续跑

- HTML 解析、URL 扫描、图片下载、图文对提取和多数 Danqing 步骤均支持并行。
- `--workers`、`--jobs` 和 `--max-parallel` 应按机器 CPU、内存和网络能力调整。
- 图片下载和图文对生成支持 `--resume`，中断后可继续执行。
- 大规模下载建议使用 `--splits` 和 `--index` 拆分到多个进程或机器。
