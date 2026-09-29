import jieba
import math
import os
from collections import defaultdict
from tqdm import tqdm
import re
from pathlib import Path

output_dir = os.environ.get("DANQING_OUTPUT_DIR", "outputs/final/danqing/2015_v2")

def load_text_file(file_path):
    """加载文本文件，返回行列表"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f]

def build_word_frequency(lines):
    """构建全局词频统计"""
    word_freq = defaultdict(int)
    total_words = 0
    
    print("正在构建全局词频统计...")
    for line in tqdm(lines):
        words = jieba.lcut(line)
        for word in words:
            word_freq[word] += 1
        total_words += len(words)
    
    return word_freq, total_words

def load_word_frequency(file_path):
    """从文件加载词频统计，并过滤掉标点符号和空白组成的词"""
    word_freq = defaultdict(int)
    total_words = 0
    filtered_words = []  # 用于保存过滤掉的词

    print(f"正在加载词频统计文件: {file_path}...")
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            parts = line.rsplit(':', 1)
            if len(parts) == 2:
                word = parts[0].strip()
                freq = int(parts[1])
                # 判断词是否包含字母、数字或汉字
                if re.search(r'[\w\u4e00-\u9fa5]', word):
                    word_freq[word] = freq
                    total_words += freq
                else:
                    # 收集被过滤的词
                    filtered_words.append(word)
            else:
                print(f"警告：词频文件格式不正确，跳过行：{line.strip()}")
        print("total_words:", total_words)
    
    # 保存过滤掉的词到文件
    if filtered_words:
        filtered_file = os.path.splitext(file_path)[0] + "_filtered.txt"
        with open(filtered_file, 'w', encoding='utf-8') as f:
            for word in filtered_words:
                f.write(f"{word}\n")
        print(f"过滤掉的词已保存至: {filtered_file}")
    
    return word_freq, total_words


def calculate_entropy(sentence, word_freq, total_words):
    """计算句子的信息熵，词频表中没有的词赋0"""
    words = jieba.lcut(sentence)
    entropy = 0.0

    for word in words:
        freq = word_freq.get(word, 0)  # 如果词不在词频表中，freq为0
        if freq > 0:
            prob = freq / total_words
            if prob > 0:
                entropy -= prob * math.log2(prob)
        else:
            # 对于词频表中没有的词，可以赋予一个极小的概率（例如1e-10）或直接跳过
            # 这里选择直接跳过
            continue
    avg_entropy = entropy / len(words) if words else 0.0
    return avg_entropy

def filter_sentences_by_entropy(input_file, entropy_threshold, max_lines=10000000, word_freq=None, total_words=None, word_freq_file=None):
    """
    过滤句子基于信息熵
    参数:
        input_file: 输入文本文件路径
        entropy_threshold: 信息熵阈值
        max_lines: 最大处理行数
        word_freq: 全局词频统计（可选）
        total_words: 总词数（可选）
        word_freq_file: 词频文件路径（可选）
    """
    # 优先尝试从文件加载词频统计
    if word_freq is None or total_words is None:
        if word_freq_file and os.path.exists(word_freq_file):
            word_freq, total_words = load_word_frequency(word_freq_file)
        else:
            # 如果没有提供词频统计或文件不存在，则加载全部文本并构建词频
            lines = load_text_file(input_file)
            word_freq, total_words = build_word_frequency(lines)
            # 如果提供了词频文件路径但文件不存在，保存词频统计
            if word_freq_file:
                with open(word_freq_file, 'w', encoding='utf-8') as f:
                    for word, freq in word_freq.items():
                        f.write(f"{word}:{freq}\n")
                print(f"词频统计保存至: {word_freq_file}")
    
    # 准备输出文件
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    output_dir = Path(input_file).parent
    output_file = output_dir / f"{base_name}_xinxishang_{entropy_threshold:.8f}.txt"
    index_file = output_dir / f"{base_name}_xinxishang_index_{entropy_threshold:.8f}.txt"
    low_entropy_file = output_dir / f"{base_name}_low_xinxishang_{entropy_threshold:.8f}.txt"
    print(f"高信息熵行号保存至: {index_file}")
    # 加载全部文本
    lines = load_text_file(input_file)
    
    # 处理前max_lines行数据
    high_entropy_lines = []
    high_entropy_indices = []
    low_entropy_lines = []
    
    print(f"正在计算句子信息熵并过滤 (阈值: {entropy_threshold})...")
    for idx, line in enumerate(tqdm(lines[:max_lines])):
        entropy = calculate_entropy(line, word_freq, total_words)
        if entropy > entropy_threshold:
            high_entropy_lines.append(line)
            high_entropy_indices.append(idx)
        else:
            low_entropy_lines.append(line)
    
    # 保存结果
    with open(output_file, 'w', encoding='utf-8') as f_out:
        f_out.write("\n".join(high_entropy_lines))
    
    with open(index_file, 'w', encoding='utf-8') as f_idx:
        f_idx.write("\n".join(map(str, high_entropy_indices)))
    
    with open(low_entropy_file, 'w', encoding='utf-8') as f_low:
        f_low.write("\n".join(low_entropy_lines))
    
    print(f"处理完成！")
    print(f"总行数: {len(lines)}")
    print(f"处理行数: {min(len(lines), max_lines)}")
    print(f"高信息熵句子数量: {len(high_entropy_lines)}")
    print(f"高信息熵句子保存至: {output_file}")
    print(f"高信息熵行号保存至: {index_file}")
    print(f"低信息熵句子保存至: {low_entropy_file}")
    
    return high_entropy_lines, high_entropy_indices, low_entropy_lines, word_freq, total_words

if __name__ == "__main__":
    # 设置输入文件路径
    input_file = f"{output_dir}/char_clean.txt"
    
    # 设置最大处理行数
    max_lines = 10000000
    
    # 设置不同的信息熵阈值
    entropy_thresholds = [0.00025]
    
    # 构建全局词频文件路径
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    word_freq_file = str(Path(input_file).with_name("word_freq.txt"))
    
    # 对不同阈值运行过滤并保存结果
    for threshold in entropy_thresholds:
        filter_sentences_by_entropy(input_file, threshold, max_lines, word_freq_file=word_freq_file)
