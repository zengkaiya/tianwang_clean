/***********************************************************************
 * @ Add an method to get the ipaddress just used in printable format.
 *					02/12/2004	18:46
 * @ Change a int var to unsigned to avoid warning message using gcc 3.2
 * 					10/22/2003	16:15 
 * @ Add one output operator to CHost, and test it in the main().
 *					10/22/2003	15:40
 ************************************************************************/
#include "host.h"
#include <netdb.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <iostream>
using namespace std;

bool 
CHost::DNS(const string &name)
{
	oname.clear();
	valias.clear();
	vaddress.clear();
	// Maybe gethostbyname() should be replaced by getaddrinfo();
	struct hostent *phost = gethostbyname(name.c_str());
	if (0!=phost){
		oname=phost->h_name;
		for (char** pptr=phost->h_aliases; *pptr!=0; pptr++)
			valias.push_back(*pptr);
		for (char**pptr=phost->h_addr_list; *pptr!=0; pptr++)
			vaddress.push_back(string(*pptr, phost->h_length));
		addrtype = phost->h_addrtype;
		return true;
	}
	return false;
}


CHost::CHost() : idx(0)
{
}

CHost::CHost(const string& name) : idx(0)
{
	DNS(name);
}

CHost::~CHost()
{
}

string
CHost::address() const
{
	if (vaddress.size() < 1) 
		return "";
	return vaddress[idx];
}

string
CHost::next() 
{
	if (vaddress.size() < 1)
		return "";
	idx = (idx+1) % vaddress.size();
	return vaddress[idx];
}



string CHost::paddr() 
{
	const char* r = inet_ntop(addrtype, address().c_str(), dst, sizeof(dst));
	if (r)
		return r;
	else
		return "";
}

ostream& 
operator<<(ostream& os, const CHost &host)
{
	os<<"oname:"<<host.oname<<endl;
	unsigned i;
	os<<"alias:"<<endl;
	for (i=0; i<host.valias.size(); i++)
		os<<host.valias[i]<<endl;
	os<<"address:"<<endl;
	char dst[256];
	for (i=0; i<host.naddr(); i++)
	{
		os<<inet_ntop(host.addrtype, host.vaddress[i].c_str(), dst, sizeof(dst))<<endl;
	}
	return os;
}

