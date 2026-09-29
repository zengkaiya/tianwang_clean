# 图片质量过滤
### 过滤策略
- 将纯色图片、模糊图片、信息熵较低的图片过滤

纯色图片：  
![纯色图片](../典型噪声图片/纯色图片.jpg#pic_center)  
模糊图片：  
![模糊图片](../典型噪声图片/模糊图片.jpg#pic_center)
低信息熵图片：  
![模糊图片](../典型噪声图片/低信息熵.jpg#pic_center)

### 运行代码
#### img_quality.py
- 输入路径为上一步中得到的xinxishang
- 输出符合要求的索引：blur_entory_indices.txt

#### readrecwithtxt.py
- 输入xinxishagn.rec，blur_entory_indices.txt
- 输出img_quality.rec