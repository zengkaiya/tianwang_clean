#include "util.h"
#include "memory.hpp"
#include <sys/stat.h>
#include <sstream>
#include <assert.h>
#include <cctype>
#include <climits>
#include <stdexcept>
#include <errno.h>
#include <limits>

using std::numeric_limits;
using std::ostringstream;
using std::runtime_error;

string 
tolower(string const &s)
{
	string res(s);
	for (unsigned i = 0; i<res.size(); i++)
	{
		res[i] = tolower(res[i]);
	}
	return res;
}

string 
toupper(string const &s)
{
	string res(s);
	for (unsigned i = 0; i<res.size(); i++)
	{
		res[i] = toupper(res[i]);
	}
	return res;
}

int 
file_size(const string &file_name)
{
	struct stat info;
	if (0 != stat(file_name.c_str(), &info))
		return -1;
	return info.st_size;
}

istream& 
operator>>(istream& is, token& t)
{
	is>>std::ws;
	char ch;
	while (is.get(ch))
	{
		if (isalpha(ch) || ch=='_' || (isdigit(ch) && !t.empty()))
		{
			t.push_back(ch);
		}
		else {
			is.unget();
			break;
		}
	}
	if (!t.empty() && is.eof())
		is.clear(is.rdstate() & ~std::ios::failbit);
	return is;
}

//
// escape with backslash is not supported here.
//
istream& 
operator>>(istream& is, quoted_string& qs)
{
	char ch;
	if (!(is>>ch))
		return is;
	if (ch == '\'' || ch == '\"')
	{
		qs.quote = ch;
	}
	else 
	{
		is.unget();
		is.setstate(std::ios::failbit);
		return is;
	}
	qs.unquote.clear();
	while (is.get(ch) && ch!=qs.quote)
		qs.unquote.push_back(ch);
	return is;
}

//
// Remove blanks at begin and end, replace sequence blanks with one SPACE
//
#if 0
string 
compress_blank(const string &in, const char* encode)
{
	wstring wIn = wc(encode, in);
	wstring wOut;
	bool accept_blank=false;
	for (size_t i=0; i<wIn.size(); i++)
	{
		if (iswspace(wIn[i]) 
		   || wIn[i]==L'\xA0') // &nbsp;
		{
			if (accept_blank)
			{
				wOut.push_back(L' ');
				accept_blank = false;
			}
			continue;
		}
		wOut.push_back(wIn[i]);
		accept_blank = true;
	}
	if (iswspace(wOut[wOut.size()-1]) 
		|| wOut[wOut.size()-1]==L'\xA0') // &nbsp;
		wOut.resize(wOut.size()-1);
	return mb(encode, wOut);
}
#endif //0

