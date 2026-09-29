import os

output_dir = os.environ.get("DANQING_OUTPUT_DIR", "outputs/final/danqing/2015_v2")

# 假设 index_file.txt 中是索引
# data_file.txt 中是所有数据
index_file = f"{output_dir}/noun_indices.txt"
data_file = f"{output_dir}/image_text_pairs.txt"
output_file = f"{output_dir}/jiebaclean.txt"

# 读取所有数据行
with open(data_file, 'r') as f:
    data_lines = f.readlines()

# 读取索引并提取对应行
with open(index_file, 'r') as f:
    indices = [int(line.strip()) for line in f if line.strip().isdigit()]

# 提取并保存
with open(output_file, 'w') as f:
    for idx in indices:
        if 0 <= idx < len(data_lines):
            f.write(data_lines[idx])
