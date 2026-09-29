import mxnet as mx
import numpy as np
import os
import sys
import multiprocessing
import logging
import csv
from tqdm import tqdm
import numpy as np
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cn_clip_tokenizer import _tokenizer

# 参数设置
output_dir = os.environ.get("DANQING_OUTPUT_DIR", "outputs/final/danqing/2015_v2")
rec_path = f"{output_dir}/nsfw.rec"
idx_path = f"{output_dir}/nsfw.idx"
output_csv = f"{output_dir}/count.csv"
output_txt = f"{output_dir}/unk_index.txt"
# 为每个进程设置日志记录器
def setup_logger(chunk_id):
    logger = logging.getLogger(f"chunk_{chunk_id}")
    logger.setLevel(logging.INFO)
    
    log_file = f"{output_dir}/progress_unk_chunk_{chunk_id}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.ERROR)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

# 重定向tqdm输出到日志记录器
class TqdmToLogger:
    def __init__(self, logger):
        self.logger = logger
        
    def write(self, message):
        message = message.replace('\r', '').replace('\n', '')
        if message.strip():
            self.logger.info(message)
            
    def flush(self):
        pass

# 判断是否是中文字符
def is_chinese_char(char):
    return '\u4e00' <= char <= '\u9fff' or '0'<= char <='9'

# 处理一个数据块的函数
def process_chunk(chunk_args, rec_path, idx_path):
    chunk_id, indices = chunk_args
    output_file = f"{output_dir}/chunk_results_{chunk_id}.csv"
    txt_file = f"{output_dir}/chunk_indices_{chunk_id}.txt"
    logger = setup_logger(chunk_id)
    tqdm_logger = TqdmToLogger(logger)
    sys.stdout = tqdm_logger
    sys.stderr = tqdm_logger
    # 每个进程创建自己的REC文件读取器
    rec_data = mx.recordio.MXIndexedRecordIO(idx_path, rec_path, 'r')
    tokenizer = _tokenizer
    
    results = []
    for idx in tqdm(indices, desc=f"Chunk {chunk_id}"):
        try:
            s = rec_data.read_idx(idx)
            header, _ = mx.recordio.unpack(s)
            token_roberta = header.label[:52]
            
            token_roberta_non_zero = token_roberta[token_roberta != 0]
            count_100 = np.sum(token_roberta_non_zero == 100)
            total_elements = len(token_roberta_non_zero)
            ratio = count_100 / total_elements if total_elements != 0 else 0
            
            text_char_list = tokenizer.convert_ids_to_tokens(token_roberta)
            text_raw = ''.join(text_char_list)
            text_raw = text_raw.replace('[CLS]', '').replace('[SEP]', '').replace('[PAD]', '').replace('#', '').strip()
            text_raw_without_unk = text_raw.replace('[UNK]', '')
            chinese_count = 0
            non_chinese_count = 0
            for char in text_raw_without_unk:
                if is_chinese_char(char):
                    chinese_count += 1
                else:
                    non_chinese_count += 1
            
            chinese_ratio = chinese_count / (chinese_count + non_chinese_count) if (chinese_count + non_chinese_count) > 0 else 0
            
            results.append({
                "index": idx,
                "count_100": count_100,
                "total_non_zero": total_elements,
                "unk_ratio": ratio,
                "chinese_count": chinese_count,
                "non_chinese_count": non_chinese_count,
                "chinese_ratio": chinese_ratio
            })
        except Exception as e:
            logger.error(f"处理记录 {idx} 时出错: {e}")
    
    # 保存结果到CSV
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["index", "count_100", "total_non_zero", "unk_ratio", "chinese_count", "non_chinese_count", "chinese_ratio"])
        writer.writeheader()
        writer.writerows(results)
    filtered_indices = [str(r["index"]) for r in results
                        if r["count_100"] <= 5 and r["chinese_ratio"] > 0.3]

    with open(txt_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(filtered_indices))

    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__
    
    logger.info(f"Chunk {chunk_id} completed with {len(results)} results")
    
    return chunk_id, len(results)

# 合并所有分块结果
def merge_results(num_chunks, output_file):
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["index", "count_100", "total_non_zero", "unk_ratio", "chinese_count", "non_chinese_count", "chinese_ratio"])
        writer.writeheader()
        
        for i in range(num_chunks):
            chunk_file = f"{output_dir}/chunk_results_{i}.csv"
            if os.path.exists(chunk_file):
                with open(chunk_file, 'r', newline='', encoding='utf-8') as cf:
                    reader = csv.DictReader(cf)
                    writer.writerows(reader)
                os.remove(chunk_file)  # 删除临时文件


def merge_results_txt(num_chunks, output_file):
    with open(output_file, 'w', encoding='utf-8') as outf:
        for i in range(num_chunks):
            txt_file = f"{output_dir}/chunk_indices_{i}.txt"
            if os.path.exists(txt_file):
                with open(txt_file, 'r', encoding='utf-8') as inf:
                    content = inf.read()
                    outf.write(content)
                    if content and not content.endswith('\n'):
                        outf.write('\n')   # 保证文件末尾换行
                os.remove(txt_file)
# 主函数
def parallel_process_rec_file(rec_path, idx_path, num_processes=8):
    rec_data = mx.recordio.MXIndexedRecordIO(idx_path, rec_path, 'r')
    total_indices = len(rec_data.keys)
    indices = list(range(total_indices))
    
    # 将索引分割成多个块
    chunks = np.array_split(indices, num_processes)
    chunk_args = [(i, list(chunk)) for i, chunk in enumerate(chunks)]
    
    # 创建进程池
    pool = multiprocessing.Pool(processes=num_processes)
    process_func = partial(process_chunk, rec_path=rec_path, idx_path=idx_path)
    
    # 并行处理
    results = []
    for result in pool.imap_unordered(process_func, chunk_args):
        chunk_id, count = result
        print(f"Chunk {chunk_id} completed with {count} results")
        results.append(count)
    
    pool.close()
    pool.join()
    
    # 合并结果
    merge_results(num_chunks=num_processes, output_file=output_csv)
    merge_results_txt(num_chunks=num_processes, output_file=output_txt)
    print(f"All chunks completed. Total results: {sum(results)}")
    print(f"Results merged to {output_csv}")

if __name__ == "__main__":
    num_processes = 64
    parallel_process_rec_file(rec_path, idx_path, num_processes)
