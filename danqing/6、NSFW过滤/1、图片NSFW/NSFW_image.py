import os
import io
import time
import threading

import torch
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader, DistributedSampler

from transformers import AutoModelForImageClassification
from PIL import Image
from tqdm import tqdm

output_dir = os.environ.get("DANQING_OUTPUT_DIR", "outputs/final/danqing/2015_v2")

from timm.data.transforms_factory import create_transform
from torchvision.transforms import Compose
from timm.data import resolve_data_config
from timm.models import get_pretrained_cfg

import mxnet as mx


Image.MAX_IMAGE_PIXELS = None


class RecordIOImageDataset(Dataset):
    def __init__(self, rec_path, idx_path, processor):
        self.rec_path = rec_path
        self.idx_path = idx_path
        self.processor = processor

        # 只在初始化阶段读取 keys，然后关闭，避免长期共享 RecordIO 句柄
        rec_data = mx.recordio.MXIndexedRecordIO(
            self.idx_path,
            self.rec_path,
            "r"
        )
        self.all_keys = sorted(list(rec_data.keys))
        rec_data.close()

        # 每个 Dataset 实例自己懒加载 reader
        self.rec_data = None

    def _get_rec_data(self):
        if self.rec_data is None:
            self.rec_data = mx.recordio.MXIndexedRecordIO(
                self.idx_path,
                self.rec_path,
                "r"
            )
        return self.rec_data

    def __len__(self):
        return len(self.all_keys)

    def __getitem__(self, idx):
        key = self.all_keys[idx]

        try:
            rec_data = self._get_rec_data()
            s = rec_data.read_idx(key)

            if s is None:
                return {
                    "ok": False,
                    "key": key,
                    "error": "read_idx returned None"
                }

            try:
                header, img_data = mx.recordio.unpack(s)
            except Exception as e:
                return {
                    "ok": False,
                    "key": key,
                    "error": f"recordio unpack failed: {repr(e)}"
                }

            if img_data is None or len(img_data) == 0:
                return {
                    "ok": False,
                    "key": key,
                    "error": "empty image bytes"
                }

            try:
                img = Image.open(io.BytesIO(img_data)).convert("RGB")
                img.load()
            except Exception as e:
                return {
                    "ok": False,
                    "key": key,
                    "error": f"PIL image decode failed: {repr(e)}"
                }

            try:
                inputs = self.processor(img)
            except Exception as e:
                return {
                    "ok": False,
                    "key": key,
                    "error": f"image transform failed: {repr(e)}"
                }

            return {
                "ok": True,
                "key": key,
                "inputs": inputs
            }

        except Exception as e:
            return {
                "ok": False,
                "key": key,
                "error": f"unknown dataset error: {repr(e)}"
            }


def safe_collate_fn(batch):
    valid_items = []
    bad_items = []

    for item in batch:
        if item is None:
            continue

        if item.get("ok", False):
            valid_items.append(item)
        else:
            bad_items.append(item)

    if len(valid_items) == 0:
        return None, bad_items

    keys = [item["key"] for item in valid_items]
    imgs = [item["inputs"] for item in valid_items]
    imgs = torch.stack(imgs, dim=0)

    return (keys, imgs), bad_items


def load_model(model_path, device):
    kwargs = {}

    # 新版 transformers 推荐 dtype；如果当前版本不支持，会 fallback 到 torch_dtype
    try:
        model = AutoModelForImageClassification.from_pretrained(
            model_path,
            dtype=torch.bfloat16
        ).to(device)
    except TypeError:
        model = AutoModelForImageClassification.from_pretrained(
            model_path,
            torch_dtype=torch.bfloat16
        ).to(device)

    model.eval()
    return model


def run_model_classifier(
    rank,
    model,
    loader,
    output_dir,
    idx_to_label,
    device="cuda:0"
):
    device = next(model.parameters()).device

    # 每个 GPU / 线程写自己的结果文件，避免多个线程同时写同一个文件
    local_category_files = {
        label: open(
            os.path.join(output_dir, f"{label}_rank{rank}.txt"),
            "w",
            encoding="utf-8"
        )
        for label in idx_to_label.values()
    }

    bad_file = open(
        os.path.join(output_dir, f"bad_image_indices_rank{rank}.txt"),
        "w",
        encoding="utf-8"
    )

    selected_count = 0
    bad_count = 0

    try:
        with torch.inference_mode():
            for data, bad_items in tqdm(loader, desc=f"{device}"):
                # 记录坏图
                if bad_items:
                    for item in bad_items:
                        bad_file.write(f"{item.get('key')}\t{item.get('error')}\n")
                        bad_count += 1

                # 当前 batch 全是坏图
                if data is None:
                    continue

                keys, batch = data
                batch = batch.to(device, non_blocking=True)

                outputs = model(batch)
                logits = outputs.logits

                probabilities = F.softmax(logits, dim=-1)
                max_indices = torch.argmax(probabilities, dim=1)

                for key, idx in zip(keys, max_indices):
                    label = idx_to_label[idx.item()]
                    local_category_files[label].write(f"{key}\n")
                    selected_count += 1

    finally:
        for f in local_category_files.values():
            f.close()

        bad_file.close()

    print(
        f"Rank {rank} finished, processed={selected_count}, bad={bad_count}"
    )


def merge_rank_files(output_dir, labels, num_gpus):
    for label in labels:
        merged_path = os.path.join(output_dir, f"{label}.txt")

        with open(merged_path, "w", encoding="utf-8") as out_f:
            for rank in range(num_gpus):
                part_path = os.path.join(output_dir, f"{label}_rank{rank}.txt")

                if not os.path.exists(part_path):
                    continue

                with open(part_path, "r", encoding="utf-8") as in_f:
                    for line in in_f:
                        out_f.write(line)

                os.remove(part_path)

    bad_merged_path = os.path.join(output_dir, "bad_image_indices.txt")

    with open(bad_merged_path, "w", encoding="utf-8") as out_f:
        for rank in range(num_gpus):
            part_path = os.path.join(output_dir, f"bad_image_indices_rank{rank}.txt")

            if not os.path.exists(part_path):
                continue

            with open(part_path, "r", encoding="utf-8") as in_f:
                for line in in_f:
                    out_f.write(line)

            os.remove(part_path)


def main():
    # 路径配置
    output_dir = os.environ.get("DANQING_OUTPUT_DIR", "outputs/final/danqing/2015_v2")
    rec_path = f"{output_dir}/img_quality.rec"
    idx_path = f"{output_dir}/img_quality.idx"
    model_path = "models/nsfw_image_detector"

    os.makedirs(output_dir, exist_ok=True)

    # 推理配置
    batch_size = 256
    num_gpus = 8

    # 先用 0，稳定优先；跑通后可尝试改成 2 或 4
    num_workers = 4 # 不需要太大

    if not torch.cuda.is_available():
        print("CUDA 不可用，将使用 CPU")
        num_gpus = 1

    available_gpus = torch.cuda.device_count() if torch.cuda.is_available() else 0

    if torch.cuda.is_available():
        num_gpus = min(num_gpus, available_gpus)

    print(f"使用 GPU 数量: {num_gpus}")

    # 标签映射
    idx_to_label = {
        0: "neutral",
        1: "low",
        2: "medium",
        3: "high"
    }

    # 加载预处理配置
    cfg = get_pretrained_cfg("eva02_base_patch14_448.mim_in22k_ft_in22k_in1k")
    processor: Compose = create_transform(
        **resolve_data_config(cfg.__dict__)
    )

    print("创建 dataloader")
    loaders = []

    for rank in range(num_gpus):
        dataset = RecordIOImageDataset(
            rec_path=rec_path,
            idx_path=idx_path,
            processor=processor
        )

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
            num_workers=num_workers,
            pin_memory=True,
            collate_fn=safe_collate_fn
        )

        loaders.append(loader)

    print("dataloader 创建完成")

    print("创建 model")
    models = []

    for rank in range(num_gpus):
        if torch.cuda.is_available():
            device = f"cuda:{rank}"
        else:
            device = "cpu"

        model = load_model(model_path, device)
        models.append(model)

    print("model 创建完成")

    threads = []
    start_time = time.time()

    for rank in range(num_gpus):
        if torch.cuda.is_available():
            device = f"cuda:{rank}"
        else:
            device = "cpu"

        thread = threading.Thread(
            target=run_model_classifier,
            args=(
                rank,
                models[rank],
                loaders[rank],
                output_dir,
                idx_to_label
            ),
            kwargs={
                "device": device
            },
            name=f"Thread-{rank}"
        )

        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

    merge_rank_files(
        output_dir=output_dir,
        labels=list(idx_to_label.values()),
        num_gpus=num_gpus
    )

    total_time = time.time() - start_time

    print(f"总处理时间: {total_time:.2f} 秒")
    print(f"分类结果已输出到:")
    for label in idx_to_label.values():
        print(f"  {os.path.join(output_dir, label + '.txt')}")

    print(f"坏图记录已输出到:")
    print(f"  {os.path.join(output_dir, 'bad_image_indices.txt')}")


if __name__ == "__main__":
    main()
