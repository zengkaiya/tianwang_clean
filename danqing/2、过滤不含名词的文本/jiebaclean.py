import argparse
import time
from multiprocessing import Pool, cpu_count

import jieba
import jieba.posseg as pseg
from tqdm import tqdm

# 提前加载模型
jieba.enable_paddle()
print("分词模型已加载")

def analyze_pos_batch(lines):
    """批量分析多行文本"""
    results = []
    for line in lines:
        stripped_line = line.strip()
        if not stripped_line:
            results.append(False)
            continue
            
        words = pseg.cut(stripped_line, use_paddle=True)
        has_noun = any(flag.startswith('n') for _, flag in words)
        results.append(has_noun)
    return results

def process_chunk(args):
    """处理单个数据块"""
    start_line, lines = args
    # 批量分析
    results = analyze_pos_batch(lines)
    # 收集包含名词的行号
    noun_lines = []
    for i, has_noun in enumerate(results):
        if has_noun:
            # 保存全局行号（从0开始计数）
            noun_lines.append(str(start_line + i))
    return noun_lines

def save_noun_line_numbers(txt_path, output_numbers_path, workers=None, chunk_size=5000, encoding="utf-8"):
    total_start = time.time()
    
    # 1. 读取文件
    with open(txt_path, 'r', encoding=encoding) as f:
        all_lines = f.readlines()
    total_lines = len(all_lines)
    print(f"读取文件完成，总行数: {total_lines}")
    
    # 2. 准备分块
    num_cores = workers or max(1, cpu_count() - 1)
    if num_cores <= 0:
        raise ValueError("workers must be positive")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    chunks = []
    for i in range(0, total_lines, chunk_size):
        chunk_lines = all_lines[i:i+chunk_size]
        chunks.append((i, chunk_lines))  # (全局起始行号, 行列表)
    
    print(f"分块数: {len(chunks)} | 每块行数: {chunk_size} | 使用进程数: {num_cores}")
    
    # 3. 处理并行任务
    pool_start = time.time()
    with Pool(num_cores) as pool:
        # 使用imap_unordered获取结果流
        results_gen = pool.imap_unordered(process_chunk, chunks)
        
        # 4. 流式写入结果 - 关键修正！
        processed_chunks = 0
        with open(output_numbers_path, 'w', encoding='utf-8') as out_file:
            for result in tqdm(results_gen, total=len(chunks), desc="分析词性", unit="chunk", dynamic_ncols=True):
                if result:  # 如果有结果
                    out_file.write('\n'.join(result) + '\n')
                processed_chunks += 1
    
    total_time = time.time() - total_start
    print(f"处理完成! 总耗时: {total_time:.2f}秒")
    print(f"结果已保存至: {output_numbers_path}")

def build_parser():
    parser = argparse.ArgumentParser(description="Filter text lines that contain at least one noun.")
    parser.add_argument(
        "--input",
        default="outputs/2013_2014/danqing/image_text_pairs.txt",
        help="Input text file; line numbers are zero-based.",
    )
    parser.add_argument(
        "--output",
        default="outputs/2013_2014/danqing/noun_indices.txt",
        help="Output file for noun-containing line numbers.",
    )
    parser.add_argument("--workers", type=int, default=max(1, cpu_count() - 1))
    parser.add_argument("--chunk-size", type=int, default=5000)
    parser.add_argument("--encoding", default="utf-8")
    return parser


if __name__ == '__main__':
    args = build_parser().parse_args()
    save_noun_line_numbers(
        txt_path=args.input,
        output_numbers_path=args.output,
        workers=args.workers,
        chunk_size=args.chunk_size,
        encoding=args.encoding,
    )
