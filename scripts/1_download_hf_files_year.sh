#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

REPO_TYPE="dataset"
HF_TOKEN_VALUE="${HF_TOKEN:-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}"
DEFAULT_MAX_PARALLEL=8
OUTPUT_ROOT="$PROJECT_ROOT/data"

REPOSITORIES=(
  "OpenDCAI/PKU_TianWang|$PROJECT_ROOT/data/PKU_TianWang/repo_file_list.cache.txt"
  "OpenDCAI/PKU_TianWang2|$PROJECT_ROOT/data/PKU_TianWang2/repo_file_list.cache.txt"
  "OpenDCAI/PKU_TianWang3|$PROJECT_ROOT/data/PKU_TianWang3/repo_file_list.cache.txt"
)

usage() {
  cat <<'EOF'
Usage:
  HF_TOKEN=<hf_token> ./scripts/1_download_hf_files_year.sh <year> <count> [options]

Examples:
  HF_TOKEN=<hf_token> ./scripts/1_download_hf_files_year.sh 2014 100
  HF_TOKEN=<hf_token> ./scripts/1_download_hf_files_year.sh 2014 all
  HF_TOKEN=<hf_token> ./scripts/1_download_hf_files_year.sh 2014 100 --seed 42
  HF_TOKEN=<hf_token> ./scripts/1_download_hf_files_year.sh 2014 100 --max-parallel 16

Arguments:
  year                   Four-digit year, for example 2014.
  count                  Positive number of random packages, or "all".

Options:
  --seed <int>           Random seed for reproducible sampling.
  --max-parallel <int>  Parallel download workers (default: 8).
  --dry-run              Only print selected paths, do not download.
  -h, --help             Show this message.
EOF
}

if [[ $# -lt 2 || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  [[ $# -lt 2 ]] && exit 1 || exit 0
fi

YEAR="$1"
COUNT="$2"
shift 2

if [[ ! "$YEAR" =~ ^[0-9]{4}$ ]]; then
  echo "year must be a four-digit number" >&2
  exit 1
fi

if [[ "$COUNT" != "all" && ! "$COUNT" =~ ^[0-9]+$ ]]; then
  echo "count must be a positive integer or all" >&2
  exit 1
fi
if [[ "$COUNT" != "all" && "$COUNT" -le 0 ]]; then
  echo "count must be a positive integer or all" >&2
  exit 1
fi

MAX_PARALLEL="$DEFAULT_MAX_PARALLEL"
SEED=""
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --seed)
      [[ $# -lt 2 ]] && { echo "--seed requires a value" >&2; exit 1; }
      SEED="$2"
      shift 2
      ;;
    --max-parallel)
      [[ $# -lt 2 ]] && { echo "--max-parallel requires a value" >&2; exit 1; }
      MAX_PARALLEL="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ ! "$MAX_PARALLEL" =~ ^[0-9]+$ ]] || [[ "$MAX_PARALLEL" -le 0 ]]; then
  echo "--max-parallel must be a positive integer" >&2
  exit 1
fi

if [[ -n "$SEED" && ! "$SEED" =~ ^-?[0-9]+$ ]]; then
  echo "--seed must be an integer" >&2
  exit 1
fi

if ! command -v hf >/dev/null 2>&1; then
  echo "Missing required command: hf" >&2
  exit 1
fi
if [[ -z "$HF_TOKEN_VALUE" ]]; then
  echo "HF_TOKEN is required" >&2
  exit 1
fi

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/tw_hf_year.XXXXXX")"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

SELECTED_FILE="$TMP_DIR/selected.tsv"
YEAR_OUTPUT_DIR="$OUTPUT_ROOT/$YEAR"

python3 - "$YEAR" "$COUNT" "$SEED" "$SELECTED_FILE" "${REPOSITORIES[@]}" <<'PY'
import random
import re
import sys
from pathlib import Path

year = sys.argv[1]
count = sys.argv[2]
seed = sys.argv[3]
output_file = Path(sys.argv[4])
repository_specs = sys.argv[5:]

pattern = re.compile(r"^[A-Za-z](\d{4})\d{2}/Web_Raw\.")
candidates = []

for spec in repository_specs:
    repo_id, cache_name = spec.split("|", 1)
    cache_path = Path(cache_name)
    if not cache_path.is_file():
        raise SystemExit(f"Cache file not found: {cache_path}")

    with cache_path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            repo_path = raw_line.strip()
            match = pattern.match(repo_path)
            if match and match.group(1) == year:
                candidates.append((repo_id, repo_path))

if not candidates:
    raise SystemExit(f"No Web_Raw packages found for year {year}")

# Avoid downloading the same repository path twice if a cache contains duplicates.
candidates = sorted(set(candidates))

if count == "all":
    selected = candidates
else:
    count = int(count)
    if count > len(candidates):
        raise SystemExit(
            f"Requested {count} packages, but only {len(candidates)} found for {year}"
        )
    rng = random.Random(int(seed)) if seed else random.Random()
    selected = rng.sample(candidates, count)
    selected.sort()

with output_file.open("w", encoding="utf-8") as f:
    for repo_id, repo_path in selected:
        f.write(f"{repo_id}\t{repo_path}\n")

print(f"Candidates for {year}: {len(candidates)}")
print(f"Selected packages: {len(selected)}")
PY

SELECTED_LIST_OUT="$YEAR_OUTPUT_DIR/selected_packages.tsv"
mkdir -p "$YEAR_OUTPUT_DIR"
cp "$SELECTED_FILE" "$SELECTED_LIST_OUT"

echo "Selected list saved to: $SELECTED_LIST_OUT"
sed -n '1,10p' "$SELECTED_FILE"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "Dry-run enabled. No download performed."
  exit 0
fi

echo "Starting downloads with max parallel: $MAX_PARALLEL"
running_jobs=0

while IFS=$'\t' read -r repo_id repo_path; do
  [[ -z "$repo_path" ]] && continue
  echo "Downloading [$repo_id]: $repo_path"
  hf download \
    "$repo_id" \
    "$repo_path" \
    --repo-type "$REPO_TYPE" \
    --token "$HF_TOKEN_VALUE" \
    --local-dir "$YEAR_OUTPUT_DIR" &

  running_jobs=$((running_jobs + 1))
  if [[ "$running_jobs" -ge "$MAX_PARALLEL" ]]; then
    wait -n
    running_jobs=$((running_jobs - 1))
  fi
done < "$SELECTED_FILE"

wait
echo "Downloaded packages to: $YEAR_OUTPUT_DIR"
