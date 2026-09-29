#ifndef _PAT_TW_RAW_H_032207
#define _PAT_TW_RAW_H_032207
#include <ostream>
#include <string>
#include "http_reply.h"
using std::string;
using std::ostream;

class CTWRaw
{
public:
	CTWRaw()
	{}
	CTWRaw(const string &u, const string &ip, const CHttpReply &r);
public:
	typedef map<string, string> ext_type;
	ext_type ext;
	string version;
	string url;
	string date;
	string ipaddr;
	CHttpReply reply;
};

ostream& operator<<(ostream &os, const CTWRaw &raw);
istream& operator>>(istream &is, CTWRaw &raw);

#endif // _PAT_TW_RAW_H_032207

