/**************************************************************************
 * @ If the network address is not available, network_add() return an empty
 *   string.				11/14/2003	16:36
 **************************************************************************/
#ifndef _PAT_HOST_H_030620
#define _PAT_HOST_H_030620

#include <vector>
#include <string>
#include <iostream>

using std::string;
using std::vector;
using std::ostream;

class CHost{
public:
	CHost();
	CHost(const string& name);

	bool DNS(const string& name);
	virtual ~CHost();
	string address() const;
	string next();
	string paddr() ;
	unsigned naddr() const
	{
		return vaddress.size();
	}
	int type() const
	{
		return addrtype;
	}

	friend ostream& operator<<(ostream& os, const CHost &host);

private:
	string oname;
	vector<string> valias;
	vector<string> vaddress;
	int idx;
	int addrtype;
	char dst[256];
};

ostream& 
operator<<(ostream& os, const CHost &host);

#endif //_PAT_HOST_H_030620
