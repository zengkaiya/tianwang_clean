import re
import os
from tqdm import tqdm  # 导入 tqdm

def clean_news_text(text):
    """
    全面清理新闻文本中的图片相关信息：
    1. 删除开头的"資料圖片："
    2. 删除"供圖"及其后面的所有内容
    3. 删除"韓聯社"及其后面的所有内容
    4. 删除"（圖片嚴禁轉載複製）"版权声明

    新增功能：
    如果按正则匹配删除后该行为空，则将该行改为NULL

    参数:
        text (str): 要处理的文本内容

    返回:
        str: 清理后的文本
    """
    # 将文本按行分割以便逐行处理
    lines = text.split('\n')
    cleaned_lines = []

    for line in lines:
        # 第一步：删除开头的"資料圖片："
        line = re.sub(r'^资料图片：', '', line)
        line = re.sub(r'^资料图片', '', line)
        # 第二步：删除"供圖"及其后面的所有内容
        # line = re.sub(r'\s*([^\s]+\s*)*供圖[^\n]*', '', line)
        # line = re.sub(r'\s+[^\n]*供圖[^\n]*', '', line)
        line = re.sub(r'([^a-zA-Z\s])\s+\S*供图\S*', r'\1', line)
        # 第三步：删除"韓聯社"及其后面的所有内容
        line = re.sub(r'\s*（韩联社）[^\n]*', '', line)
        line = re.sub(r'\s*韩联社[^\n]*', '', line)

        # 第四步：删除版权声明
        line = re.sub(r'\s*（图片严禁转载复制）', '', line)
        line = re.sub(r'\s*（图片仅限南韩国内使用，严禁转载复制）', '', line)
        # 如果清理后行为空，则改为NULL
        if line.strip() == '':
            cleaned_lines.append("NULL")
        else:
            # 清理行首空格
            cleaned_line = re.sub(r'^\s+', '', line)
            cleaned_lines.append(cleaned_line)

    # 将处理后的行重新组合成文本
    cleaned_text = '\n'.join(cleaned_lines)

    # 移除连续多个空行
    cleaned_text = re.sub(r'\n\s*\n+', '\n\n', cleaned_text)

    return cleaned_text.strip()

def remove_special_characters(text):
    # 定义正则表达式模式来匹配 emoji 和其他特殊符号
    emoji_pattern = re.compile(
        "["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map symbols
        u"\U0001F700-\U0001F77F"  # alchemical symbols
        u"\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
        u"\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
        u"\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        u"\U0001FA00-\U0001FA6F"  # Chess Symbols
        u"\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        "]+", flags=re.UNICODE
    )

    # 去除文本中的 emoji
    text = emoji_pattern.sub(r'', text)
    return text

# 对.txt 文档中的每一行进行操作
def process_txt_file(input_file_path, output_file_path):
    try:
        # 读取.txt 文档的内容
        with open(input_file_path, 'r', encoding='utf-8') as file:
            text = file.read()

        # 将文本按行分割以便逐行处理
        lines = text.split('\n')
        processed_lines = []

        # 初始化进度条
        total_lines = len(lines)
        progress_bar = tqdm(total=total_lines, desc="Processing", unit="line")

        for line in lines:
            # 对每一行调用 clean_news_text 函数进行清理
            cleaned_line = clean_news_text(line)
            # 去除特殊字符
            cleaned_line = remove_special_characters(cleaned_line)
            processed_lines.append(cleaned_line)
            
            # 更新进度条
            progress_bar.update(1)

        # 关闭进度条
        progress_bar.close()

        # 将处理后的行重新组合成文本
        processed_text = '\n'.join(processed_lines)

        # 将清理后的文本写入新的.txt 文档
        with open(output_file_path, 'w', encoding='utf-8') as file:
            file.write(processed_text)

        print(f"处理完成，结果已保存到 {output_file_path}")

    except Exception as e:
        print(f"处理文件时出错：{e}")

# 示例用法
output_dir = os.environ.get("DANQING_OUTPUT_DIR", "outputs/final/danqing/2015_v2")
input_file = f"{output_dir}/jiebaclean2simple.txt"
output_file = f"{output_dir}/cleanuselesswords.txt"
process_txt_file(input_file, output_file)
