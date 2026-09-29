# 文本NSFW过滤
### 过滤策略
- 利用 https://github.com/PaddlePaddle/PaddleHub/blob/develop/modules/README_ch.md#%E6%96%87%E6%9C%AC%E5%AE%A1%E6%A0%B8 中提供的模型进行过滤
- 根据 https://github.com/jkiss/sensitive-words 中停用词表的内容进行过滤

### 运行代码
#### nsfwtxt.py
- 输入去除纯色、模糊图片、信息熵得到的img_quality.rec
- 输出符合条件的索引：no_nsfw_words.txt

#### nsfw_tingyongci.py
- 输入去除纯色、模糊图片、信息熵得到的img_quality.rec
- 输出符合条件的索引non_keyword_indices.txt

#### handletxt.sh
- 输入为no_nsfw_words.txt、non_keyword_indices.txt
- 对其进行排序和去重，结果仍保存在原.txt