/*****************************************************************************
 * @ Add a few "clear()" to save memory.
 * 					07/07/2004	11:47
 * @ The sscanf or istream::operator>> can skip the blank characters before
 *   reading a integer. When getting chunk_len in http reply, blank characters
 *   mean an error! For detecting this error, I write a "get_hex" myself.
 *					03/01/2004	09:55
 * @ Let user can limit the size of the reply. In my GSE, some ".dat" url 
 *   pretend to be "text/plain", but is more huge than 100M. In fact they
 *   are video files and useless to me. If users don't limit the size, it 
 *   will be 2'000'000'000 defaultly. I think it's huge enough.
 *					02/27/2004	00:52
 * @ CHttpReply's output function is not for display(& debug) usage now, so 
 *   the ending "\r\n" is deleted.
 * @ Change CHttpReply's output function: non-text body will also be put to 
 *   the ostream. Output function to ofstream do the same thing, so it is 
 *   delete.	 			02/12/2004	19:12
 * @ Fix a bug. A "const char*" returned by CCommu::brecv() may be invalidated
 *   after another call to brecv(), directly or through other call such as 
 *   getline(). When fetching chunked body, I used such a invalidated pointer.
 *   HLE said some webpage in infomall lost some bytes in the end. Now this 
 *   will not happen. 
 *					01/09/2004	22:15
 * @ Take it out from http. 		12/11/2003	23:26
 ****************************************************************************/
#include "http_reply.h"
#include "url.h"
#include "cutem.h"
#include "stdexcept"
#include <sstream>
#ifdef DMALLOC 
#include "dmalloc.h"
#endif

using std::istringstream;
using std::ostringstream;
using std::runtime_error;
using std::length_error;
using std::hex;
using std::ios;

CHttpReply::CHttpReply() : max_size(2000000000), req_method("GET")
{
}

CHttpReply::CHttpReply(const string &method, int max) 
	: max_size(max), req_method(method)
{
}

int
CHttpReply::set_max_size(int max)
{
	int ret = max_size;
	max_size = max;
	return ret;
}

int 
CHttpReply::get_hex(const char* str, int n)
{
	unsigned num = 0;
	for (int i=0; i<n && i<8; i++)
	{
		char ch = str[i];
		if (ch>='A' && ch<='F')
		{
			num *= 16;
			num += ch-'A'+10;
		}
		else if (ch>='a' && ch<='f')
		{
			num *= 16;
			num += ch-'a'+10;
		}
		else if (ch>='0' && ch<='9')
		{
			num *= 16;
			num += ch-'0';
		}
		else
		{
			break;
		}
	}
	if (num > 1000000000)
		return -1;
	else 
		return num;
}

ostream& operator<<(ostream &os, const CHttpReply &reply)
{
	os<<reply.status<<"\r\n";
	for (unsigned i = 0; i<reply.headers.size(); i++)
		os<<reply.headers[i]<<"\r\n";
	os<<"\r\n";
	os<<reply.body;
	return os;
}

