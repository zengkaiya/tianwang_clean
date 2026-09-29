from tqdm import tqdm  # 引入进度条库
import os

def filter_lines_by_length_and_save_indices(input_file, output_final, output_filtered, output_indices, min_length=5, max_length=60):
    """
    根据行字符长度筛选文件内容，将符合条件的行保存到最终结果文件，不符合条件的行保存到过滤结果文件，并保存字符长度小于 min_length 的行的行号索引。

    Args:
        input_file (str): 输入文件路径。
        output_final (str): 最终结果文件路径。
        output_filtered (str): 过滤结果文件路径。
        output_indices (str): 保存字符长度小于 min_length 的行的行号索引文件路径。
        min_length (int, optional): 最小字符长度（包含）。默认为60。
        max_length (int, optional): 最大字符长度（包含）。默认为100000。
    """
    try:
        with open(input_file, 'r', encoding='utf-8') as infile:
            total_lines = sum(1 for line in infile)  # 统计文件总行数

        with open(input_file, 'r', encoding='utf-8') as infile, \
             open(output_final, 'w', encoding='utf-8') as final_out, \
             open(output_filtered, 'w', encoding='utf-8') as filtered_out, \
             open(output_indices, 'w', encoding='utf-8') as indices_out:

            line_number = 0  # 初始化行号
            short_line_numbers = []  # 保存字符长度小于 min_length 的行的行号

            # 使用 tqdm 包装进度条
            for line in tqdm(infile, total=total_lines, desc="Processing"):
                # 获取当前行的字符长度（去掉换行符）
                line_length = len(line.rstrip('\n'))

                if min_length <= line_length <= max_length:
                    # 符合条件的行写入最终结果文件
                    final_out.write(line)
                    short_line_numbers.append(str(line_number))
                else:
                    # 不符合条件的行写入过滤结果文件
                    filtered_out.write(line)
                    # 如果字符长度小于 min_length，记录行号

                line_number += 1  # 行号递增

            # 将字符长度小于 min_length 的行的行号索引写入文件
            indices_out.write('\n'.join(short_line_numbers))

        print(f"筛选完成！最终结果已保存到 '{output_final}'，过滤内容已保存到 '{output_filtered}'，字符长度小于 {min_length} 的行的行号索引已保存到 '{output_indices}'")

    except Exception as e:
        print(f"发生错误：{e}")

# 调用示例
output_dir = os.environ.get("DANQING_OUTPUT_DIR", "outputs/final/danqing/2015_v2")
filter_lines_by_length_and_save_indices(
    f'{output_dir}/cleanuselesswords.txt',
    f'{output_dir}/char_clean.txt',
    f'{output_dir}/filtered.txt',
    f'{output_dir}/char_clean_index.txt',
)
