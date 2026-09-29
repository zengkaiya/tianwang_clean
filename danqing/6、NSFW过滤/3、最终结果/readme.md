### 运行代码
#### crossing.py
- 输入为图片NSFW得到的结果neutral.txt和文本NSFW得到的结果no_nsfw_words.txt和non_keyword_indices.txt
- 求三者的交集得到最终符合条件的索引final_index.txt

#### readrecwithtxt.py
- 输入为img_quality.rec,img_quality.idx,final_index.txt
- 输出得到nsfw过滤后的结果nsfw.rec和nsfw.idx