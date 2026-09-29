/**************************************************************************
 * @ When brecv failed, he will return a non-nil pointer and you have to 
 *   check the output argument len.	03/13/2004	23:17
 * @ Use commu.brecv(delim, len) to rewrite getline, make it simpler.
 *					12/10/2003	23:37
 * @ http package is too large, so I split it into smaller pieces, such as
 *   CHttpRequest, CHttpReply. Some little objects is putted into http_bits.
 *   http.h is just a interface.	12/10/2003	23:05
 **************************************************************************/
#include "http_bits.h"
#include "util.h"
#include <sstream>
#include <cstring>
using std::istringstream;
using std::ws;

#if 0
//not used
// RFC2616[12~13]
static const char* separators = "()<>@,;:\\\"/[]?={} \t";
static bool isctl(char ch) {
	return (0<=ch && ch<=31 || ch==127);
}

static bool intoken(char ch) {
	return isascii(ch) && !strchr(separators, ch) && !isctl(ch);
}
#endif //0 

istream& operator>>(istream& is, CStatus& sta)
{
	string line;
	if (!getline(is, line))
		return is;
	if (line.empty())
	{
		is.setstate(std::ios::failbit);
		return is;
	}
	if (line[line.size() - 1] == '\r')
		line.erase(line.size() - 1);
	istringstream iss(line);
	iss >> sta.http_version >> sta.code >> ws;
	if (!iss || tolower(sta.http_version[0])!='h')
	{
		is.setstate(std::ios::failbit);
		return is;
	}
	getline(iss, sta.reason);
	return is;
}

ostream& operator<<(ostream& os, const CStatus& sta)
{
	return os<<sta.http_version<<' '<<sta.code<<' '<<sta.reason;
}

istream& operator>>(istream& is, CHeader& hea)
{
	hea.name.clear();
	hea.value.clear();

	string line;
	if (!getline(is, line))
		return is;
	if (line.empty())
	{
		is.setstate(std::ios::failbit);
		return is;
	}
	if (line[line.size() - 1] == '\r')
		line.erase(line.size() - 1);
	istringstream iss(line);
	if (!getline(iss, hea.name, ':'))
	{
		is.setstate(std::ios::failbit);
		return is;
	}
	// empty header value is acceptable. 
	iss>>ws;
	getline(iss, hea.value);
	return is;
}

ostream& operator<<(ostream& os, const CHeader& hea){
	return os<<hea.name<<": "<<hea.value;
}

string 
CHeaders::charset() const
{
	string content_type = value("Content-Type");
	string attr_name="charset=";
	string::size_type start = content_type.find(attr_name);
	if (start == string::npos)
		return "";
	start += attr_name.size();
	string::size_type end;
	for (end = start; end < content_type.size() 
	   && content_type[end] != ';' ; end ++);
	return content_type.substr(start, end - start);
}

string 
CHeaders::value(const string& name) const
{
	if (name.empty())
		return "";
	for (unsigned i=0; i<size(); i++)
		if (strcasecmp((*this)[i].name.c_str(), name.c_str())==0)
			return (*this)[i].value;
	return "";
}

vector<const string *>
CHeaders::values(const string& name) const
{
	vector<const string*> __v;
	for (unsigned i=0; i<size(); i++)
		if (strcasecmp((*this)[i].name.c_str(), name.c_str())==0)
			__v.push_back(&(*this)[i].value);
	return __v;
}

int
CHeaders::content_length() const
{
	string sLength = value("Content-Length");
	istringstream iss(sLength);
	int length;
	if (iss >> length && length >= 0)
	{
		return length;
	}
	return -1;
}

CDisposition
CHeaders::content_disposition() const
{
	CDisposition disposition;
	istringstream iss(value("Content-Disposition"));
	if (!getline(iss, disposition.type, ';'))
		return disposition;
	if (disposition.type == "attachment")
	{
		string para_name;
		iss>>ws;
		if (!getline(iss, para_name, '='))
			return disposition;
		if (para_name == "filename")
		{
			quoted_string qs;
			if (iss>>qs)
				disposition.filename = qs.unquote;
		}
	}
	return disposition;
}

media_t
CHeaders::mtype() const
{
	const string &content_type = value("Content-Type");
	if (strcasestr(content_type.c_str(), "text") != 0)
		return m_text;
	if (strcasestr(content_type.c_str(), "pdf") != 0)
		return m_pdf;
	if (strcasestr(content_type.c_str(), "postscript") != 0)
		return m_ps;
	if (strcasestr(content_type.c_str(), "msword") != 0)
		return m_doc;
	if (strcasestr(content_type.c_str(), "image") != 0)
		return m_image;
	if (strcasestr(content_type.c_str(), "audio") != 0)
		return m_audio;
	if (strcasestr(content_type.c_str(), "video") != 0)
		return m_video;
	return m_unknown;
}

string
CHeaders::ext() const
{
	const string &content_type = value("Content-Type");
	if (content_type.empty())
		return "";
	if (strcasestr(content_type.c_str(), "text/xml") != 0)
		return "xml";
	if (strcasestr(content_type.c_str(), "text/html") != 0)
		return "html";
	if (strcasestr(content_type.c_str(), "pdf") != 0)
		return "pdf";
	if (strcasestr(content_type.c_str(), "postscript") != 0)
		return "ps";
	if (strcasestr(content_type.c_str(), "msword") != 0)
		return "doc";
	return "";
}
