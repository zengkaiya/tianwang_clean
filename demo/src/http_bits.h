#ifndef _PAT_HTTP_BITS_H_121003
#define _PAT_HTTP_BITS_H_121003
#include <ostream>
#include <istream>
#include <vector>
#include "ext.h"

using std::string;
using std::ostream;
using std::istream;
using std::vector;

class CStatus
{
public:
	CStatus() : code(0)
	{
	}
	string http_version;
	int code;
	string reason; 
};

istream& operator>> (istream& commu, CStatus& sta);
ostream& operator<< (ostream &os, const CStatus& sta);

class CHeader
{
public:
	CHeader(const char* n, const char* v): name(n), value(v)
	{
	}
	CHeader(const char* n, const string &v): name(n), value(v)
	{
	}
	CHeader()
	{
	}
	string name;
	string value;
};
istream& operator>> (istream& commu, CHeader& hea);
ostream& operator<< (ostream& os, const CHeader& hea);

class CDisposition
{
public:
	string type;  // "attachment" or "inline"
	string filename;
};

class CHeaders : public vector<CHeader>
{
public:
	string value(const string& name) const;
	vector<const string*> values(const string& name) const;

	media_t mtype() const;
	string charset() const;
	int content_length() const;
	CDisposition content_disposition() const;
	string ext() const;
private:
	static string nulstr;
};

#endif // _PAT_HTTP_BITS_H_121003
