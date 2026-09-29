import os
import torch
from torch.utils.data import Dataset, DataLoader, DistributedSampler
from PIL import Image
import mxnet as mx
import time
from tqdm import tqdm
import threading
import sys
import paddlehub as hub
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from cn_clip_tokenizer import _tokenizer

Image.MAX_IMAGE_PIXELS = None

class RecordIODataset(Dataset):
    def __init__(self, rec_path, idx_path, tokenizer):
        self.rec_path = rec_path
        self.idx_path = idx_path
        self._local = threading.local()
        self._readers = {}
        self._readers_lock = threading.Lock()

        # 只在初始化时读取 keys，随后立即关闭临时 reader。
        rec_data = mx.recordio.MXIndexedRecordIO(idx_path, rec_path, 'r')
        self.keys = list(rec_data.keys)
        rec_data.close()
        self.tokenizer = tokenizer

    def _get_reader(self):
        reader = getattr(self._local, "reader", None)
        if reader is None:
            reader = mx.recordio.MXIndexedRecordIO(self.idx_path, self.rec_path, 'r')
            self._local.reader = reader
            with self._readers_lock:
                self._readers[(os.getpid(), threading.get_ident())] = reader
        return reader

    def close(self):
        with self._readers_lock:
            readers = list(self._readers.values())
            self._readers.clear()
        for reader in readers:
            reader.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def __len__(self):
        return len(self.keys)

    def __getitem__(self, idx):
        key = self.keys[idx]
        s = self._get_reader().read_idx(key)
        header, _ = mx.recordio.unpack(s)

        token_ids = [int(tid) for tid in header.label[:52]]

        # 移除特殊标记
        if token_ids and token_ids[0] == 101:
            token_ids = token_ids[1:]
        if token_ids and token_ids[-1] == 102:
            token_ids = token_ids[:-1]

        text_char_list = self.tokenizer.convert_ids_to_tokens(token_ids)
        text_raw = ''.join(text_char_list)
        text_raw = text_raw.replace('[CLS]', '').replace('[SEP]', '').replace('[PAD]', '').replace('#','').strip()

        return text_raw, key

# 指定路径
output_dir = os.environ.get("DANQING_OUTPUT_DIR", "outputs/final/danqing/2015_v2")
rec_path = f"{output_dir}/img_quality.rec"
idx_path = f"{output_dir}/img_quality.idx"

dataset = RecordIODataset(rec_path, idx_path, _tokenizer)
batch_size = 64
num_gpus = 8

loaders = []
print("创建dataloader")
for rank in range(num_gpus):
    sampler = DistributedSampler(
        dataset,
        num_replicas=num_gpus,
        rank=rank,
        shuffle=False
    )
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        sampler=sampler,
        num_workers=2,
        pin_memory=True
    )
    loaders.append(loader)
print("dataloader创建完成")

def worker_fn(loader, device_id):

    os.environ['CUDA_VISIBLE_DEVICES'] = str(device_id)

    model = hub.Module(name="porn_detection_cnn")
    zero_keys = []

    for texts, keys in tqdm(loader, desc=f"GPU {device_id}"):
        try:
            results = model.detection(texts=list(texts), use_gpu=True, batch_size=len(texts))
            for res, key in zip(results, keys):
                if res["porn_detection_label"] == 0:
                    zero_keys.append(int(key))
        except Exception as e:
            print(f"[GPU {device_id}] Error: {e}")

    # 保存结果
    output_path = f"{output_dir}/zero_indices_gpu_{device_id}.txt"
    with open(output_path, "w") as f:
        for key in zero_keys:
            f.write(f"{key}\n")
    print(f"[GPU {device_id}] 完成，保存 {len(zero_keys)} 个结果到 {output_path}")

def merge_results(num_gpus, output_file=f"{output_dir}/no_nsfw_words.txt"):
    all_keys = set()
    
    print(f"开始合并{num_gpus}个结果文件...")
    for i in range(num_gpus):
        file_path = f"{output_dir}/zero_indices_gpu_{i}.txt"
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                keys = [int(line.strip()) for line in f.readlines()]
                all_keys.update(keys)
            print(f"已加载文件 {file_path}，包含 {len(keys)} 个键")
        else:
            print(f"警告: 文件 {file_path} 不存在")
    
    # 排序并保存
    sorted_keys = sorted(all_keys)
    with open(output_file, "w") as f:
        for key in sorted_keys:
            f.write(f"{key}\n")
    
    print(f"合并完成! 总共 {len(sorted_keys)} 个键，已保存到 {output_file}")
    return output_file


# === 主函数 ===
threads = []
start_time = time.time()

for i in range(num_gpus):
    thread = threading.Thread(
        target=worker_fn,
        args=(loaders[i], i),  # 修复：只使用位置参数
        name=f"Thread-{i}"
    )
    thread.start()
    threads.append(thread)

# 等待所有线程完成
for thread in threads:
    thread.join()

dataset.close()

total_time = time.time() - start_time
print(f"总处理时间: {total_time:.2f}秒")

merge_results(num_gpus)
