import mxnet as mx
import time
import threading
from tqdm import tqdm
import queue
import os

output_dir = os.environ.get("DANQING_OUTPUT_DIR", "outputs/final/danqing/2015_v2")

# 记录开始时间
start_time = time.time()

# 创建 RecordIO 读取器
read_record = mx.recordio.MXIndexedRecordIO(
    f"{output_dir}/simple.idx",
    f"{output_dir}/simple.rec",
    "r",
)

# 读取索引文件并加载到内存中
with open(f"{output_dir}/txt_index.txt", "r") as f:
    indices = [int(line.strip()) for line in f]

# 创建新的 RecordIO 写入器来存储选定的记录
write_record = mx.recordio.MXIndexedRecordIO(
    f"{output_dir}/xinxishang.idx",
    f"{output_dir}/xinxishang.rec",
    "w",
)

# 创建 tqdm 进度条
pbar = tqdm(total=len(indices), desc="处理进度")

# 创建一个队列，用于存储读取到的记录
record_queue = queue.Queue()
read_completed = threading.Event()

# 定义读取线程函数
def read_thread():
    for i, old_idx in enumerate(indices):
        item = read_record.read_idx(old_idx)
        record_queue.put((i, item))
    read_completed.set()

# 定义写入线程函数
def write_thread():
    while not (record_queue.empty() and read_completed.is_set()):
        if not record_queue.empty():
            idx, item = record_queue.get()
            write_record.write_idx(idx, item)
            pbar.update(1)
        else:
            time.sleep(0.1)

# 创建读取线程和写入线程
read_t = threading.Thread(target=read_thread)
write_t = threading.Thread(target=write_thread)

# 启动读取线程和写入线程
read_t.start()
write_t.start()

# 等待读取线程和写入线程完成
read_t.join()
write_t.join()

# 关闭 tqdm 进度条
pbar.close()

# 关闭读取器和写入器
read_record.close()
write_record.close()

# 记录结束时间
end_time = time.time()

# 计算运行时间
runtime = end_time - start_time

print(f"\n代码运行时间：{runtime:.2f} 秒")
