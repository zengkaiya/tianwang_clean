/********************************************************************
 * @ Used as an Interface of CURI for search engine. 
 *    1. cut fragment first.
 *    2. escape non-uric charector.
 * 						07/30/2004	22:29
 ********************************************************************/
#ifndef _PAT_URL_H_100402
#define _PAT_URL_H_100402
#include <iostream>
#include <set>
#include "ext.h"
#include "uri.h"

using std::less;
using std::set;

bool isIP(const string &host);

class CURL : public CURI
{
public:
	CURL();
	CURL(const std::string& urlstr, const CURL* base=0);
	int init(const string &urlstr);
	string str(bool show_default_port=false) const;
	virtual ~CURL();
	string protocol() const;
	string host() const;
	string localpath() const;
	string localstr() const
	{
		return localpath()+query();
	}
	string site() const;
	static string host2site(const string &host);
	static string host2domain(const string &host);
	int port() const;
	string fragment() const;
	string hostport() const;
	static string hostport(const string &scheme, const string &host, int port);
	static void split(const string &scheme, const string &hostport, string &host, int& port);
	string newurl(const char* relative) const;
	media_t mtype() const;
	operator void*() const
	{
		if (scheme.empty())
			return (void*)0;
		else return (void*)1;
	}
private:
	string query() const;
	string correct(const string &urlstr);
	static string::size_type match_domain(const string &host);
private:
	static CExt __ext;
};

class is_uric_no_escape
{
public:
	is_uric_no_escape(){}
	void * operator()(int ch);
private:
	static const int size = 128;
	static unsigned char map[size];
};

#endif /* _PAT_URL_H_100402 */
