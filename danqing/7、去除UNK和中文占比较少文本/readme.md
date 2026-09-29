# 根据UNK数量和中文占比过滤
### 过滤策略
- 过滤掉句子中UNK占比大于5个及中文占比小于0.3的数据
- 去除掉剩余句子中的UNK

### 运行代码
#### unkclean_count.py
- 输入NSFW过滤后得到的nsfw.idx,nsfw.rec
- 输出符合条件的索引unk_index.txt

#### readrecwithtxt.py
- 输入nsfw.idx,nsfw.rec,unk_index.txt
- 输出过滤后的结果clean_unk_words.idx,clean_unk_words.rec

#### unkclean.py
- 输入clean_unk_words.idx,clean_unk_words.rec
- 输出将文本中UNK去除后的最终结果final.idx,final.rec