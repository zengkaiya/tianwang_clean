import os
from opencc import OpenCC

output_dir = os.environ.get("DANQING_OUTPUT_DIR", "outputs/final/danqing/2015_v2")

def is_chinese_char(char):
    """判断字符是否为中文字符（包括简体和繁体）"""
    # 基本汉字范围：U+4E00 - U+9FFF (CJK Unified Ideographs)
    # 扩展A区：U+3400 - U+4DBF (CJK Extension A)
    # 扩展B区：U+20000 - U+2A6DF (CJK Extension B) 等
    code = ord(char)
    return (
        (0x4E00 <= code <= 0x9FFF) or    # 基本汉字
        (0x3400 <= code <= 0x4DBF) or     # 扩展A区
        (0x20000 <= code <= 0x2A6DF) or   # 扩展B区
        (0x2A700 <= code <= 0x2B73F) or  # 扩展C区
        (0x2B740 <= code <= 0x2B81F) or  # 扩展D区
        (0x2B820 <= code <= 0x2CEAF)     # 扩展E区
    )

def process_file_with_stats(input_file, output_file):
    """处理文件并返回统计信息"""
    cc = OpenCC('t2s')  # 繁体转简体转换器
    
    # 初始化统计变量
    total_chars = 0          # 总中文字符数
    traditional_count = 0    # 繁体字数
    simplified_count = 0     # 简体字数
    processed_lines = 0
    
    try:
        with open(input_file, 'r', encoding='utf-8') as infile, \
             open(output_file, 'w', encoding='utf-8') as outfile:
            
            for line in infile:
                # 转换当前行
                simplified_line = cc.convert(line)
                
                # 写入转换后的行
                outfile.write(simplified_line)
                
                # 统计当前行
                for orig_char, conv_char in zip(line, simplified_line):
                    if is_chinese_char(orig_char):
                        total_chars += 1
                        
                        if orig_char != conv_char:
                            traditional_count += 1
                        else:
                            simplified_count += 1
                
                # 更新进度
                processed_lines += 1
                if processed_lines % 1000 == 0:
                    print(f"已处理 {processed_lines} 行...")
    
    except Exception as e:
        print(f"处理过程中发生错误: {str(e)}")
        return None, None, None, None
    
    return total_chars, traditional_count, simplified_count, processed_lines

def print_statistics(total_chars, traditional_count, simplified_count, lines):
    """打印详细的统计信息"""
    if total_chars is None:
        return
    
    print("\n" + "="*50)
    print("文本处理统计报告")
    print("="*50)
    
    # 基本统计
    print(f"总行数: {lines:,}")
    print(f"总中文字符数: {total_chars:,}")
    print(f"繁体字数量: {traditional_count:,}")
    print(f"简体字数量: {simplified_count:,}")
    
    # 比例计算
    if total_chars > 0:
        trad_percent = (traditional_count / total_chars) * 100
        simpl_percent = (simplified_count / total_chars) * 100
        
        print("\n比例分析:")
        print(f"繁体字比例: {trad_percent:.2f}%")
        print(f"简体字比例: {simpl_percent:.2f}%")
        
        # 语言类型判断
        if trad_percent > 70:
            print("\n语言类型: 繁体中文为主")
        elif simpl_percent > 70:
            print("\n语言类型: 简体中文为主")
        else:
            print("\n语言类型: 简繁混合")
    else:
        print("\n警告: 文件中未检测到中文字符")

if __name__ == "__main__":

    input_file = f"{output_dir}/jiebaclean.txt"    # 输入的繁体文本文件
    output_file = f"{output_dir}/jiebaclean2simple.txt"  # 输出的简体文本文件
    
    print("开始处理文件...")
    stats = process_file_with_stats(input_file, output_file)
    
    if stats[0] is not None:
        print("\n处理完成!")
        print(f"简体文本已保存至: {output_file}")
        print_statistics(*stats)
    else:
        print("处理失败，请检查错误信息")
