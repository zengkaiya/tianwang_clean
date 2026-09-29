#include "ext.h"
#include <ctype.h>

static const char* image_ext[] = {
	"gif", "ai", "jpg", "tif", "png", "jpe", "bmp", "ico", "icojpg","jpeg", 
	"pcx", "tiff", "wmf", "psd", "tga", "pic", "pcd", "dib", "rle", "iff",
	"lbm", "jif", "dcx", "xls", 0
};

static const char* audio_ext[] = {
	"wav", "mp3", "mid", "wma", "mp2", "mp1", "aif", "au", "snd", "cda",
	"mpl", "m3u", "mjf", "as", "voc", "xm", "s3m", "stm", "mod", "dsm",
	"far", "ult", "mtm", "mpga", "mpa","669","aac","mp4","vgf","pls","xpl"
	, 0
};

static const char* video_ext[] = {
	"rm", "ra", "avi", "asf", "wmv", "mpg", "mpe", "mpeg",  "mpv", 
	"mov", "qt", "ram","rmm", "rmj","vob","asx","wvx","wm","m1v",
	"wmp","ivf","smi","mpv2", "rmvb", "rmva", "swf", "flv", 0
};

static const char* binary_ext[] = {
	/* compressed */
	"tar", "zip", "gtar", "ustar", "gz", "z", "arj", "rar", "iso", "tgz",
	"cab","arc","b64","bhx","hqx","lzh","mim","taz","tz","uu","uue","xxe",
	/* document */
	"ppt","exl","mdb","asa","rtf","wri","pps",
	"dot","pot","wps",
	/* binary */
	"bin", "lib", "a", "o", "dll", "exe", "rpm","com","ocx","out","bat","class", "scr",
	/* other */
	"reg", "latex", "css", "frt"
	/* "cgi" is deleted. */
	,0
};

static const char* text_ext[] = {
	"txt", "html", "htm", "mht", "shtml","js", 0
};

CExt::CExt()
{
	int i;
	for (i=0; image_ext[i]!=0; i++) 
	{
		_map[image_ext[i]] = m_image;
	}
	for (i=0; audio_ext[i]!=0; i++) 
	{
		_map[audio_ext[i]] = m_audio;
	}
	for (i=0; video_ext[i]!=0; i++) 
	{
		_map[video_ext[i]] = m_video;
	}
	for (i=0; text_ext[i]!=0; i++) 
	{
		_map[text_ext[i]] = m_text;
	}
	for (i=0; binary_ext[i]!=0; i++) 
	{
		_map[binary_ext[i]] = m_binary;
	}
	_map["pdf"] = m_pdf;
	_map["ps"] = m_ps;
	_map["doc"] = m_doc;
}

media_t CExt::mtype(const string &ext)
{
	string _ext = ext;
	for (unsigned i=0; i<_ext.size(); i++)
		_ext[i] = tolower(_ext[i]);
	strmap::iterator iter;
	if ((iter=_map.find(_ext)) ==  _map.end())
		return m_unknown;
	return iter->second;
}
