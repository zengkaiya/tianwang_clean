# 图片NSFW过滤
### 过滤策略
- 利用  https://huggingface.co/Freepik/nsfw_image_detector?not-for-all-audiences=true 模型过滤涉黄、涉政等敏感信息

### 运行代码
#### NSFW_image.py
- 输入去除纯色、模糊图片、信息熵得到的img_quality.rec
- 输出得到对应风险等级的图片的索引  
中性图片索引：neutral.txt  
低风险图片索引：low.txt  
中风险图片索引：medium.txt  
高风险图片索引：high.txt

#### handletxt.sh
- 输入为存放不同风险图片索引的路径
- 对得到的索引进行排序和去重，结果仍保存在原.txt