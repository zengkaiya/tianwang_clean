#ifndef _PAT_EXT_H_083003
#define _PAT_EXT_H_083003
#include <string>
#include <map>

using std::string;
using std::map;
using std::less;

enum media_t {
	m_text=0, m_image=1, m_pdf=2, m_ps=3, m_video=4, m_audio=5
	, m_binary=6, m_doc=7, m_unknown=8, m_media_t_count=9
};

class CExt{
public:
	CExt();
	virtual ~CExt()
	{}
	media_t mtype(const string &ext);
private:
	typedef map<string, media_t, less<string> > strmap;
	strmap _map;
};
#endif // _PAT_EXT_H_083003
