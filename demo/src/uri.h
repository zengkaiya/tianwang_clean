#ifndef _PAT_URI_H_071704_
#define _PAT_URI_H_071704_
#include <string>
#include <list>
#include <ostream>
#include <vector>
using std::vector;
using std::list;
using std::string;
using std::ostream;
class URIFlexLexer;

class segment 
{
public:
	segment(const string &s) : str(s)
	{}
public:
	string str;
	vector<string> params;
};

class CURI
{
public:
	friend class URIFlexLexer;
	CURI();
	virtual ~CURI()
	{}
	int parse(const string &uristr);  // 0 means OK.
	void normalize();
	static void normalize_escaped(string &str);
	void toabs(const CURI &base);
	string local_ext() const;
	bool isAbs() const
	{
		return !scheme.empty() && !host.empty();
	}
	static int default_port(const string &scheme);
	ostream& explain(ostream &os);
// protected:
	string scheme;
	string userinfo;
	string host;
	int port;
	// There will be ambiguity if reg_name;
	//string reg_name;
	string opaque_part;
	list<segment> path_segments;
	vector<string> query;
	string fragment;
};
extern CURI* global_URI;

#endif // _PAT_URI_H_071704_
