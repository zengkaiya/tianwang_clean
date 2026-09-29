# 过滤不包含名词的文本
### 过滤策略
- 利用jieba分词并判断词性，将文本描述中不包含名词的数据过滤

![不含名词1](../典型噪声图片/不含名词1.jpg#pic_center)  
对应文本：컨텐츠이미지입니다

![不含名词2](../典型噪声图片/不含名词2.jpg#pic_center)  
对应文本：Image Source | topstarnews 提供

### 运行代码
#### jiebaclean.py
- 读取根据图片长宽比过滤得到的test.txt
- 运行后得到符合要求的索引，保存在：包含名词的行号.txt中
- 命令行执行 sort -n 包含名词的行号.txt -o 包含名词的行号.txt,对得到的索引进行排序

#### readrecwithtxt.py
- 根据jiebaclean.py得到的包含名词的行号.txt，从test.rec中提取符合要求的结果保存成jiebaclean.rec

#### readtxtwithtxt.py
- 根据jiebaclean.py得到的.txt索引结果，从test.txt中提取符合要求的结果保存成新的jiebaclean.txt
