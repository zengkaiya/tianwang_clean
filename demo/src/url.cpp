/***************************************************************************
 * @ Add a new protocol: "file://... "
 *					05/11/2004	09:00
 * @ Suggested by Su Hang, all generic url other than http://... and ftp://...
 *   Will be accepted.  Generic url has the same format as "scheme://host:port
 *   /local "				02/25/2004	11:02
 ***************************************************************************/
#include "url.h"
//#include "cutil.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <stdint.h>
#include <sstream>
#include <vector>
#ifdef DMALLOC
#include "dmalloc.h"
#endif

using std::vector;
using std::pair;
bool isIP(const string &h)
{
	for (unsigned i=0; i<h.size(); i++)
	{
		if ((h[i]<'0' || h[i]>'9') && h[i]!='.')
		return false;
	}
	return true;
}


CURL::CURL()
{
}

CURL::CURL(const std::string& urlstr, const CURL *base)
{
	if (0 != init(urlstr))
		return;
	if (base != 0)
	{
		toabs(*base);
		this->normalize();
	}
}

string
CURL::query() const
{
	string res;
	for(unsigned i=0; i<CURI::query.size(); i++)
		res += CURI::query[i];
	return res;
}

string
CURL::fragment() const
{
	return CURI::fragment;
}

using std::istringstream;
using std::istream;

static const char* cat_domain[] = {
	"com"	// Commercial
	, "co"	// Commercial
	, "net" // Network
	, "org" // Non-profit Organization
	, "edu" // Educational
	, "gov" // Government
	, "int" // International
	, "mil" // Military
	, "biz" // Bussiness
	, "info"// Enterprise With Infomation
	, "tv"	// Televion
	, "pro" // Professional
	//, "name" 
	//, "museum"
	//, "coop"
	, "aero" // airlines
	, "rec"  // Enterprise in Pleasure
	, "store" // Enterprise who sells products
	, "web" // Enterprise Who Are Web related
	, "firm" // Enterprise
	, "arts" // Enterprise In Culture and Pleasure
	, "arpa" // Old style Arpanet
	, "nom"  // Peronal
	, 0
};

static const char* reg_domain[] = {
	"cn", "jp", "uk", "ca", "la", "cc", "sc", "id", "de", "be", "ie"
	, "ve", "sg", "ch"
	, "sh", "dk", "hk", "il", "nl", "pl", "fm", "in", "co", "tr"
	, "br", "fr", "gr", "es", "us", "ws", "at", "it", "pt", "au"
	, "ru", "lv", "tw", "mx", "nz"
	, 0
};

class CTopCat : public set<string, less<string> >
{
public:
	CTopCat()
	{
		for (int i=0; cat_domain[i]!=0; i++)
		{
			this->insert(cat_domain[i]);
		}
	}
	virtual ~CTopCat()
	{}
};

class CTopReg : public set<string, less<string> >
{
public:
	CTopReg()
	{
		for (int i=0; reg_domain[i]!=0; i++)
		{
			this->insert(reg_domain[i]);
		}
	}
	virtual ~CTopReg()
	{}
};

static CTopCat top_cat;
static CTopReg top_reg;

string
CURL::correct(const string &urlstr)
{
	string result;
	bool isFragment = false;
	for (unsigned i=0
		; i<urlstr.size() && urlstr[i] !='\0' 
		; i++)
	{
		is_uric_no_escape is_uric_no_escape;
		if (urlstr[i] == '#' && !isFragment)
		{
			result += urlstr[i];
			isFragment = true;
		}
		else if (is_uric_no_escape(urlstr[i]))
		{
			result += urlstr[i];
		}
		else if (urlstr[i] == '\\')
		{
			result += '/';
		}
		else if (urlstr[i] == '%' 
			&& isxdigit(urlstr[i+1]) && isxdigit(urlstr[i+2]))
		{
			result.append(urlstr, i, 3);
			i += 2;
		}
		else 
		{	
			int m = (unsigned char)urlstr[i];
			int n = m % 16;
			m /= 16;
			result += '%';
			result += (m > 9 ? 'A'+ m - 10 : '0' + m - 0);
			result += (n > 9 ? 'A'+ n - 10 : '0' + n - 0);
		}
	}
	return result;
}

int 
CURL::init(const string &urlstr)
{
	if (urlstr.size() > 256)  // Discard loooong URLs
		return -1;
	string input = correct(urlstr);
	if (0 != this->parse(input))
		return -2;
	this->normalize();
	return 0;
}

CURL::~CURL()
{
}

using std::ostringstream;

string 
CURL::str(bool show_default_port) const
{
	ostringstream oss;
	if (!scheme.empty())
	{
		oss<<scheme<<':';
	}
	if (!CURI::host.empty())
	{
		oss<<"//";
		if (!userinfo.empty())
		{
			oss<<userinfo<<'@';
		}
		oss<<CURI::host;
		if (show_default_port || default_port(scheme)!=CURI::port)
			oss<<':'<<CURI::port;
	}
	oss<<localstr();
/*
	if (!fragment.empty())
		oss<<'#'<<fragment;
*/
	return oss.str();
}

string 
CURL::protocol() const
{
	return scheme;
}

string 
CURL::host() const
{
	return CURI::host;
}

string
CURL::hostport() const
{
	if (host().empty())
		return "";
	return hostport(scheme, host(), port());
}

string 
CURL::hostport(const string &scheme, const string &host, int port)
{
	std::ostringstream oss;
	oss<<host;
	if (port != default_port(scheme))
		oss<<':'<<port;
	return oss.str();
}

void
CURL::split(const string &scheme, const string &hostport
	, string &host, int &port)
{
	port = 0;
	string::size_type pos = hostport.find(':');
	if (pos != string::npos)
	{
		host.assign(hostport, 0, pos);
		port = atoi(hostport.c_str()+pos+1);
	}
	else
		host = hostport;
	if (port <= 0)
		port = default_port(scheme);
	return ;
}

string 
CURL::localpath() const
{
	string path;
	list<segment>::const_iterator citer;
	for (citer=path_segments.begin(); citer!=path_segments.end(); citer++)
	{
		path.append(citer->str);
		for (unsigned i=0; i<citer->params.size(); i++)
		{
			if (citer->params[i].find("jsessionid=") != string::npos)
				continue;
			path.append(citer->params[i]);
		}
	}
	return path;
}

string
CURL::host2site(const string &host) 
{
	string::size_type domain_pos = match_domain(host);
	if (domain_pos == string::npos)
	{
		if (isIP(host))
		{
			string::size_type pos = 0;
			for (int i=0; i<3; i++)
			{
				if (host[pos]=='.' && pos!= 0)
					pos ++;
				pos = host.find('.', pos);
				if (pos == string::npos)
				{
					pos = host.size();
					break;
				}
			}
			return string(host, 0, pos);
		}
		// not ip address
		if (host.size() == 0)
			return "Unknown";
		string::size_type site_pos = host.rfind('.', host.size()-1);
		if (site_pos == string::npos)
			site_pos = 0;
		else 
			site_pos ++;
		if (site_pos >= host.size())
			return "Unknown";
		return string(host, site_pos, host.size() - site_pos);
	}
	string::size_type site_pos = domain_pos;
	for (int i=0; i<2; i++)
	{
		if (site_pos == string::npos || site_pos == 0)
			break;
		if (host[site_pos]=='.')
			site_pos --;
		site_pos = host.rfind('.', site_pos);
	}
	if (site_pos == string::npos || site_pos == 0)
		return host;
	return string(host, site_pos+1);
}

/********************************************************************
 Return value: the position of the domain in the host string.
 	= string::npos  if not find.
 ********************************************************************/
string::size_type
CURL::match_domain(const string &host)
{
	string::size_type pos1, pos, pos2;
	pos1 = host.size();
	vector<pair<string, unsigned> > segs;
	while (segs.size() < 2)
	{
		
		if (pos1 == string::npos)
			break;
		if (pos1 == 0)
			break;
		pos2 = pos1;
		pos1=host.rfind('.', pos1-1);
		if (pos1 == string::npos)
			pos = 0;
		else
			pos = pos1+1;
		if (pos < pos2)
		{
			string seg(host, pos, pos2 - pos);
			segs.push_back(pair<string, unsigned>(seg, pos));
		}
	}
	if (segs.size() >= 2 && top_reg.count(segs[0].first) != 0 && 
		top_cat.count(segs[1].first) != 0)
	{ // com.cn , org.cn ...
		return segs[1].second;
	}
	if (segs.size() >= 1 && (top_reg.count(segs[0].first) != 0 ||
		top_cat.count(segs[0].first) != 0) )
	{ // com , org , cn ...
		return segs[0].second;
	}
	return string::npos;
}

string
CURL::host2domain(const string &host) 
{
	string::size_type pos = match_domain(host);
	if (pos == string::npos)
	{
		if (isIP(host))
		{
			return "IP_Address";
		}
		return "Unknown";
	}
	return string(host, pos);
}

string
CURL::site() const
{
	return host2site(CURI::host);
}

int 
CURL::port() const
{
	return CURI::port;
}

string
CURL::newurl(const char* relative) const
{
	CURL rel(relative, this);
	return rel.str();
}

CExt CURL::__ext;

media_t CURL::mtype() const
{
	return __ext.mtype(this->local_ext());
}

unsigned char is_uric_no_escape::map[128] = {
/*	0, 1, 2, 3, 4, 5, 6, 7, 8, 9, a, b, c, d, e, f		 */
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  /* 00-0F*/
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  /* 10-1F*/
	0, 1, 0, 0, 1, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,  /* 20-2F*/
	1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 1, 0, 1,  /* 30-3F*/
	1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,  /* 40-4F*/
	1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 1,  /* 50-5F*/
	0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,  /* 60-6F*/
	1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 1, 0,  /* 70-7F*/
};

void*
is_uric_no_escape::operator()(int ch)
{
	if (ch < 0 || ch > 127)
		return (void*) 0;
	return (void*)(uintptr_t)(map[ch]);
}
