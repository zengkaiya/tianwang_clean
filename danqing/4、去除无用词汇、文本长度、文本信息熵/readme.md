# 去除无用词汇、文本长度、文本信息熵
### 过滤策略
- 利用正则匹配去除文本中的无效内容，如：资料图片，图片禁止转载等
- 根据信息熵过滤文本，过滤掉长度小于5或者大于60的文本
- 根据文本信息熵过滤掉后5%的文本

低信息熵文本:
帽子 charcoal 彩色图像-S6L12
ZEROBASEONE成员韩维辰

### 运行代码
#### zhengzetihuan.py
- 输入繁简转换的结果jiebaclean2simple.py
- 输出得到去除了文本中无效内容的文本cleanuselesswords.txt

#### txtclean_withchar.py
- 输入上一步得到的cleanuselesswords.txt
- 输出得到清洗后的文本：char_clean.txt，及满足条件的文本的索引：char_clean_index.txt

#### xinxishang.py
- 输入上一步得到的 char_clean.txt
- 输出高信息熵句子对应的行号 xinxishang_index_entropy.txt

#### readtxtwithtxt.py
- 输入char_clean_index.txt 和 xinxishang_index_entropy.txt
- 输出得到最终的索引txt_index.txt

#### readrecwithtxt.py
- 输入繁简体转换得到的simple.idx，simple.rec及上一步得到的txt_index.txt
- 输出得到xinxishang.idx和xinxishang.rec