#!/bin/bash

# 指定文件夹路径
folder_path="${DANQING_OUTPUT_DIR:-outputs/final/danqing/2015_v2}"

# 遍历文件夹中的所有 .txt 文件
for file in "$folder_path"/{no_nsfw_words.txt,non_keyword_indices.txt}; do
    # 检查文件是否存在且是文件
    if [ -f "$file" ]; then
        # 对文件中的数字进行排序并删除重复值
        sort -n -o "$file" "$file"    # 排序并覆盖原文件
        awk '!seen[$0]++' "$file" > temp && mv temp "$file"  # 删除重复值
        echo "已处理文件：$(basename "$file")"
    fi
done

echo "所有文件处理完成！"
