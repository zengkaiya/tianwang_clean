import os

output_dir = os.environ.get("DANQING_OUTPUT_DIR", "outputs/final/danqing/2015_v2")

def find_intersection(file1, file2, file3, output_file):
    # 读取文件内容并转换为集合
    with open(file1, 'r') as f:
        set1 = set(f.read().splitlines())
    with open(file2, 'r') as f:
        set2 = set(f.read().splitlines())
    with open(file3, 'r') as f:
        set3 = set(f.read().splitlines())
    
    # 计算交集
    intersection = set1 & set2 & set3
    
    # 将结果写入输出文件
    with open(output_file, 'w') as f:
        for item in sorted(intersection):
            f.write(f"{item}\n")

# 示例用法
file1 = f"{output_dir}/no_nsfw_words.txt"
file2 = f"{output_dir}/non_keyword_indices.txt"
file3 = f"{output_dir}/neutral.txt"
output_file = f"{output_dir}/final_index.txt"
find_intersection(file1, file2, file3, output_file)
