#ifndef _PAT_UTIL_H_20081213
#define _PAT_UTIL_H_20081213
#include <string>
#include <istream>

using std::istream;
using std::string;

string tolower(string const &s);
string toupper(string const &s);

/* ON unix/linux/mac with x86:  wc_code should be UCS-4LE, 
 * UTF-32LE is the same.
 */
int file_size(const string &file_name);
//string compress_blank(const string &in, const char* encode="UTF-8");

class token : public string
{};
istream& operator>>(istream& is, token& t);

class quoted_string 
{
public: 
	operator string() const
	{
		return quote+unquote+quote;
	}
	char quote;
	string unquote;
};
istream& operator>>(istream& is, quoted_string& q);


#endif // _PAT_UTIL_H_20081213
