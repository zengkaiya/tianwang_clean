dataset="2015_v3"
export DANQING_DATASET="$dataset"
export DANQING_OUTPUT_DIR="outputs/final/danqing/$dataset"

output_dir="$DANQING_OUTPUT_DIR"

# 第一步
python 'danqing/1、根据图片长宽比过滤/datacleanbyimage.py' \
  --input outputs/final/pairs/2015/image_text_pairs_similarity_ge_0.49.jsonl \
  --output-prefix "$output_dir/image_text_pairs" \
  --min-side 100 \
  --min-ratio 0.333333 \
  --max-ratio 3.0 \
  --workers 64 \
  --jpeg-quality 95

# 第二步
python 'danqing/2、过滤不含名词的文本/jiebaclean.py' \
  --input "$output_dir/image_text_pairs.txt" \
  --output "$output_dir/noun_indices.txt" \
  --workers 32 \
  --chunk-size 5000 \
  --encoding utf-8

sort -n "$output_dir/noun_indices.txt" \
  -o "$output_dir/noun_indices.txt"

# 需要替换目录
python "danqing/2、过滤不含名词的文本/readtxtwithtxt.py"
python "danqing/2、过滤不含名词的文本/readrecwithtxt.py"

# 第三步 需要替换目录
python "danqing/3、繁简体转换/trad2simple.py"

python "danqing/3、繁简体转换/dara2rec.py" \
    --raw-idx "$output_dir/jiebaclean.idx" \
    --raw-rec "$output_dir/jiebaclean.rec" \
    --text "$output_dir/jiebaclean2simple.txt" \
    --output-prefix "$output_dir/simple" \
    --batch-size 512 \
    --token-workers 32 \
    --prefetch-batches 2 \
    --target-length 52

# 第四步
python "danqing/4、去除无用词汇、文本长度、文本信息熵/zhengzetihuan.py"
python "danqing/4、去除无用词汇、文本长度、文本信息熵/txtclean_withchar.py"
python "danqing/4、去除无用词汇、文本长度、文本信息熵/xinxishang.py"
python "danqing/4、去除无用词汇、文本长度、文本信息熵/readtxtwithtxt.py"
python "danqing/4、去除无用词汇、文本长度、文本信息熵/readrecwithtxt.py"

# 第五步
python "danqing/5、去除纯色、模糊图片、信息熵过滤/img_quality.py"
python "danqing/5、去除纯色、模糊图片、信息熵过滤/readrecwithtxt.py"

# 第六步
python "danqing/6、NSFW过滤/1、图片NSFW/NSFW_image.py"
bash "danqing/6、NSFW过滤/1、图片NSFW/handletxt.sh"

# 这个最后跑完会有报错，可能是rec文件没有正常关闭
PADDLE_HOME="$PWD/models/paddlehub" \
python "danqing/6、NSFW过滤/2、文本NSFW/nfswtxt.py"

bash "danqing/6、NSFW过滤/2、文本NSFW/handletxt.sh"

python "danqing/6、NSFW过滤/2、文本NSFW/nsfw_tingyongci.py"

python "danqing/6、NSFW过滤/3、最终结果/crossing.py"
python "danqing/6、NSFW过滤/3、最终结果/readrecwithtxt.py"

# 第七步
python "danqing/7、去除UNK和中文占比较少文本/unkclean_count.py"
python "danqing/7、去除UNK和中文占比较少文本/readrecwithtxt.py"

python 'danqing/7、去除UNK和中文占比较少文本/unkclean.py' \
  --input-idx "$output_dir/clean_unk_words.idx" \
  --input-rec "$output_dir/clean_unk_words.rec" \
  --output-idx "$output_dir/final.idx" \
  --output-rec "$output_dir/final.rec" \
  --batch-size 256 \
  --token-workers 16 \
  --prefetch-batches 1 \
  --target-length 52
