import re
from tqdm import tqdm
import mxnet as mx
import multiprocessing
import sys
import logging
import numpy as np
import os
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from cn_clip_tokenizer import _tokenizer

output_dir = os.environ.get("DANQING_OUTPUT_DIR", "outputs/final/danqing/2015_v2")

# 关键字列表
keywords = [
    "下载", "官方网站", "官方版", "官方正版", "游戏截图", "最新版", "破解版",
    "二维码", "国产AV", "国产精品", "澳门新葡京", "国产成人",
    "点击看大图", "点击查看详细信息", "image来源", "微信图片", "图片1.png", "图片未找到", "未找到图片", "麻豆传媒"
]

words_dir = Path(__file__).resolve().parent / "sensitive-words-master"
file_paths = [
    words_dir / "广告.txt",
    words_dir / "色情类.txt",
    words_dir / "涉枪涉爆违法信息关键词_utf-8.txt",
    words_dir / "网址.txt",
    words_dir / "政治类.txt",
]

# 读取文件中的关键词并添加到列表
for file_path in file_paths:
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
                word = line.strip()
                if word:
                    keywords.append(word)
        print(f"已添加关键词来自: {file_path}")
    except Exception as e:
        print(f"读取文件 {file_path} 时出错: {e}")

print("合并后的关键词列表长度:")
print(len(keywords))

# 编译URL匹配正则表达式
url_pattern = re.compile(r'https?://\S+|www\.\S+')
combined_keywords_pattern = re.compile("|".join(map(re.escape, keywords)))

rec_path = f"{output_dir}/img_quality.rec"
idx_path = f"{output_dir}/img_quality.idx"

# 为每个进程设置日志记录器
def setup_logger(chunk_id):
    logger = logging.getLogger(f"chunk_{chunk_id}")
    logger.setLevel(logging.INFO)
    
    log_file = f"progress_chunk_{chunk_id}.log"
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

# 并行处理一个数据块的函数
def process_chunk(args, rec_path, idx_path, combined_keywords_pattern, url_pattern):
    chunk_id, indices = args
    output_file = f"{output_dir}/non_keyword_indices_{chunk_id}.txt"
    content_file = f"{output_dir}/non_keyword_contents_{chunk_id}.txt"
    
    logger = setup_logger(chunk_id)
    tqdm_logger = TqdmToLogger(logger)
    sys.stdout = tqdm_logger
    sys.stderr = tqdm_logger
    # 每个进程创建自己的REC文件读取器
    rec_data = mx.recordio.MXIndexedRecordIO(idx_path, rec_path, 'r')
    
    non_keyword_indices = []
    non_keyword_contents = []
    
    for idx in tqdm(indices, desc=f"Chunk {chunk_id}"):
        try:
            s = rec_data.read_idx(idx)
            header, _ = mx.recordio.unpack(s)
            
            token_ids = [int(tid) for tid in header.label if tid != 0]
            token_ids = token_ids[:52]
            if token_ids and token_ids[0] == 101:
                token_ids = token_ids[1:]
            if token_ids and token_ids[-1] == 102:
                token_ids = token_ids[:-1]
            text_char_list = _tokenizer.convert_ids_to_tokens(token_ids)
            text = ''.join(text_char_list)
            text = text.replace('[CLS]', '').replace('[SEP]', '').replace('[PAD]', '').replace('#', '').strip()
            
            # 检查文本是否包含关键词或 URL
            match_keyword = combined_keywords_pattern.search(text)
            match_url = url_pattern.search(text)
            
            if not (match_keyword or match_url):
                non_keyword_indices.append(f"{idx}\n")
                non_keyword_contents.append(f"{text}\n")
                
        except Exception as e:
            logger.error(f"处理记录 {idx} 时出错: {e}")
    
    # 保存结果到文件
    with open(output_file, 'w', encoding="utf-8") as f:
        f.writelines(non_keyword_indices)
    
    with open(content_file, 'w', encoding="utf-8") as f:
        f.writelines(non_keyword_contents)
    
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__
    
    logger.info(f"Chunk {chunk_id} completed with {len(non_keyword_indices)} non-keyword lines")
    
    return chunk_id, len(non_keyword_indices)

# 合并所有分块结果
def merge_results(num_chunks, output_file_indices=f"{output_dir}/non_keyword_indices.txt", output_file_contents=f"{output_dir}/non_keyword_contents.txt"):
    with open(output_file_indices, 'w', encoding="utf-8") as indices_file, \
         open(output_file_contents, 'w', encoding="utf-8") as contents_file:
        for i in range(num_chunks):
            indices_chunk_file = f"{output_dir}/non_keyword_indices_{i}.txt"
            contents_chunk_file = f"{output_dir}/non_keyword_contents_{i}.txt"
            
            if os.path.exists(indices_chunk_file):
                with open(indices_chunk_file, 'r', encoding="utf-8") as f:
                    indices_file.writelines(f.readlines())
                os.remove(indices_chunk_file)
            
            if os.path.exists(contents_chunk_file):
                with open(contents_chunk_file, 'r', encoding="utf-8") as f:
                    contents_file.writelines(f.readlines())
                os.remove(contents_chunk_file)

# 并行处理REC文件
def parallel_process_rec_file(rec_path, idx_path, combined_keywords_pattern, url_pattern, num_processes=8):
    rec_data = mx.recordio.MXIndexedRecordIO(idx_path, rec_path, 'r')
    total_lines = len(rec_data.keys)
    image_indices = list(range(total_lines))
    
    # 将索引分成多个块
    chunks = np.array_split(image_indices, num_processes)
    chunk_args = [(i, list(chunk)) for i, chunk in enumerate(chunks)]
    
    pool = multiprocessing.Pool(processes=num_processes)
    process_func = partial(process_chunk, 
                          rec_path=rec_path, 
                          idx_path=idx_path, 
                          combined_keywords_pattern=combined_keywords_pattern, 
                          url_pattern=url_pattern)
    
    results = []
    for result in pool.imap_unordered(process_func, chunk_args):
        chunk_id, count = result
        print(f"Chunk {chunk_id} completed with {count} non-keyword lines")
        results.append(count)
    
    pool.close()
    pool.join()
    
    merge_results(num_chunks=num_processes)
    print(f"Total non-keyword lines: {sum(results)}")
    print(f"Results merged to non_keyword_indices.txt and non_keyword_contents.txt")

if __name__ == "__main__":
    num_processes = 64  # 使用的进程数
    parallel_process_rec_file(rec_path, idx_path, combined_keywords_pattern, url_pattern, num_processes)
