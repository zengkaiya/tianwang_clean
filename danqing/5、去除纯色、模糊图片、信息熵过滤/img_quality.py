from tqdm import tqdm
import cv2
import mxnet as mx
import multiprocessing
import os
import numpy as np
from functools import partial
import sys
import logging
from contextlib import redirect_stdout, redirect_stderr
import csv

output_dir = os.environ.get("DANQING_OUTPUT_DIR", "outputs/final/danqing/2015_v2")

def compute_blur_score(img, size=(100, 100)):
    """计算图像模糊分数"""
    if len(img.shape) == 3:
        gray_img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    else:
        gray_img = img
    
    # small_img = cv2.resize(gray_img, size)
    return cv2.Laplacian(gray_img, cv2.CV_64F).var()

def compute_entropy(img):
    """计算图像的信息熵"""
    if len(img.shape) == 3:
        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray_img = img

    hist = cv2.calcHist([gray_img], [0], None, [256], [0, 256])
    hist = hist / hist.sum()
    entropy = -np.sum(hist * np.log2(hist + 1e-10))
    return entropy


def setup_logger(chunk_id, output_dir):
    """为每个进程设置日志记录器"""
    logger = logging.getLogger(f"chunk_{chunk_id}")
    logger.setLevel(logging.INFO)
    
    # 创建文件处理器
    log_file = os.path.join(output_dir, f"progress_chunk_{chunk_id}.log")
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    
    # 创建格式化器
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    file_handler.setFormatter(formatter)
    
    # 添加处理器到日志记录器
    logger.addHandler(file_handler)
    
    # 创建控制台处理器（可选，用于错误信息）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.ERROR)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

class TqdmToLogger:
    """重定向tqdm输出到日志记录器"""
    def __init__(self, logger):
        self.logger = logger
        
    def write(self, message):
        # 过滤掉进度条的特殊字符
        message = message.replace('\r', '').replace('\n', '')
        if message.strip():
            self.logger.info(message)
            
    def flush(self):
        pass

def process_chunk(args, rec_path, blur_threshold,PLAIN_COLOR_THRESHOLD,ENTROPY_THRESHOLD):
    """
    处理一个数据块的函数，将进度输出到日志文件
    
    Args:
        args: 包含(chunk_id, indices)的元组
        rec_path: .rec文件路径
        blur_threshold: 模糊阈值
    """
    chunk_id, indices = args
    output_dir = os.path.dirname(rec_path)
    output_file = os.path.join(output_dir, f"blur_entory_indices_{chunk_id}.txt")
    output_csv = os.path.join(output_dir, f"entropy_values_{chunk_id}.csv")
    # 设置日志记录器
    logger = setup_logger(chunk_id, output_dir)
    
    # 重定向tqdm输出到日志文件
    tqdm_logger = TqdmToLogger(logger)
    sys.stdout = tqdm_logger
    sys.stderr = tqdm_logger
    
    # 每个进程创建自己的REC文件读取器
    record = mx.recordio.MXIndexedRecordIO(
        rec_path + '.idx', 
        rec_path + '.rec', 
        'r'
    )
    
    # 处理当前数据块的所有索引
    non_blurry_indices = []
    entropy_list = []
    # 使用tqdm，但输出被重定向到日志文件
    for idx in tqdm(indices, desc=f"Chunk {chunk_id}"):
        try:
            item = record.read_idx(idx)
            header, img_str = mx.recordio.unpack(item)
            img = mx.image.imdecode(img_str).asnumpy()
            
            if img is None:
                logger.error(f"无法解码图像，索引：{idx}")
                continue

            small_img = cv2.resize(img, (100, 100))
            std_dev = np.std(small_img)
            
            if std_dev < PLAIN_COLOR_THRESHOLD:
                continue
            
            blur_score = compute_blur_score(small_img)
            if blur_score < blur_threshold:
                continue
                
            entropy = compute_entropy(small_img)
            
            entropy_list.append((idx,entropy))
            if entropy >= ENTROPY_THRESHOLD:
                non_blurry_indices.append(idx)

        except Exception as e:
            logger.error(f"Error processing index {idx}: {str(e)}")
    
    # 将结果保存到分块文件
    with open(output_file, 'w') as f:
        for idx in non_blurry_indices:
            f.write(f"{idx}\n")

    # with open(output_csv, 'w', newline='') as f_csv:
    #     writer = csv.writer(f_csv)
    #     writer.writerow(['idx', 'entropy'])
    #     for idx, ent in entropy_list:
    #         writer.writerow([idx, ent])
    # 恢复标准输出
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__
    
    logger.info(f"Chunk {chunk_id} completed with {len(non_blurry_indices)} non-blurry images")
    
    return chunk_id, len(non_blurry_indices)

def merge_results(output_file, output_dir, num_chunks):
    """合并所有分块结果文件"""
    with open(output_file, 'w') as out_f:
        for i in range(num_chunks):
            chunk_file = os.path.join(output_dir, f"blur_entory_indices_{i}.txt")
            if os.path.exists(chunk_file):
                with open(chunk_file, 'r') as in_f:
                    for line in in_f:
                        out_f.write(line)
                #删除临时文件
                os.remove(chunk_file)


def merge_csv_results(output_csv="all_entropy_values.csv", 
                      num_chunks=8
                      ):
    """
    合并所有分块生成的 CSV 文件，只保留一次表头。

    Args:
        output_csv: 最终合并后的 CSV 文件名
        num_chunks: chunk 数量
        chunk_pattern: 生成文件的命名模板，其中 {} 会被 chunk_id 替换
    """
    first = True
    with open(output_csv, 'w', newline='') as out_f:
        writer = None

        for i in range(num_chunks):
            chunk_file = f"entropy_values_{i}.csv"
            if not os.path.exists(chunk_file):
                continue

            with open(chunk_file, 'r', newline='') as in_f:
                reader = csv.reader(in_f)
                header = next(reader)  # 读表头

                if first:
                    # 只在第一个文件写入表头
                    writer = csv.writer(out_f)
                    writer.writerow(header)
                    first = False

                # 写入其余所有行
                for row in reader:
                    writer.writerow(row)

            # 删除已合并的临时文件
            os.remove(chunk_file)

    print(f"合并完成，输出文件：{output_csv}")


def parallel_process_rec_file(rec_path, blur_threshold ,PLAIN_COLOR_THRESHOLD ,ENTROPY_THRESHOLD , num_processes=8):
    """
    并行处理REC文件（支持从0开始的索引）
    
    Args:
        rec_path: .rec文件路径
        blur_threshold: 模糊阈值
        num_processes: 并行进程数
    """
    # 打开REC文件获取所有索引
    record = mx.recordio.MXIndexedRecordIO(
        rec_path + '.idx', 
        rec_path + '.rec', 
        'r'
    )
    
    # 获取所有有效索引（包括0）
    all_keys = sorted(record.keys)
    image_indices = all_keys  # 包含索引0
    
    total_images = len(image_indices)
    print(f"Total images to process: {total_images}")
    
    # 将索引分成num_processes个块
    chunks = np.array_split(image_indices, num_processes)
    chunk_args = [(i, list(chunk)) for i, chunk in enumerate(chunks)]
    
    # 创建进程池
    pool = multiprocessing.Pool(processes=num_processes)
    
    # 使用偏函数固定其他参数
    process_func = partial(process_chunk, rec_path=rec_path, blur_threshold=blur_threshold,PLAIN_COLOR_THRESHOLD = PLAIN_COLOR_THRESHOLD,ENTROPY_THRESHOLD = ENTROPY_THRESHOLD)
    
    # 并行处理所有块
    results = []
    for result in pool.imap_unordered(process_func, chunk_args):
        chunk_id, count = result
        print(f"Chunk {chunk_id} completed with {count} non-blurry images")
        results.append(count)
    
    # 关闭进程池
    pool.close()
    pool.join()
    
    # 合并结果
    output_dir = os.path.dirname(rec_path)
    merge_results(
        output_file=os.path.join(output_dir, "blur_entory_indices.txt"),
        output_dir=output_dir,
        num_chunks=num_processes,
    )
    print(f"Total non-blurry images: {sum(results)}")
    print(f"Results merged to blur_entory_indices.txt")

# 示例用法
if __name__ == "__main__":
    rec_path = f"{output_dir}/xinxishang"
    blur_threshold = 1000
    PLAIN_COLOR_THRESHOLD = 2
    ENTROPY_THRESHOLD = 3.5

    num_processes = 64
    parallel_process_rec_file(rec_path, blur_threshold, PLAIN_COLOR_THRESHOLD,ENTROPY_THRESHOLD,num_processes)
