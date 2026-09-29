/*************************************************************************
 * @ Thanks Xiehan, I fix a bug.
 *					09/26/2004	21:54
 * @ uri parser by lex. Xiehan's code is refered.
 *					07/16/2004	19:45
 *************************************************************************/
%option noyywrap
/* The followings are BNFs generating URI-refernce, taken from RFC 2396. */
/* Underscore is permitted in the hostname.				*/
URI-reference 	({absoluteURI}|{relativeURI})?("#"{fragment})?
absoluteURI	{scheme}":"({hier_part}|{opaque_part}) 
relativeURI	({net_path}|{abs_path}|{rel_path})("?"{query})?

hier_part	({net_path}|{abs_path})("?"{query})?
opaque_part	{uric_no_slash}{uric}*

uric_no_slash	{unreserved}|{escaped}|[;?:@&=+$,]

net_path	"//"{authority}{abs_path}?
abs_path	"/"{path_segments}
rel_path	{rel_segment}{abs_path}?
rel_segment	({unreserved}|{escaped}|[;@&=+$,])+

scheme		{alpha}({alpha}|{digit}|[+-.])*

authority	{server}|{reg_name}
reg_name	({unreserved}|{escaped}|[$,;:@&=+])+

server		(({userinfo}@)?{hostport})?
userinfo	({unreserved}|{escaped}|[;:&=+$,])*

hostport	{host}(":"{port})?
host		{hostname}|{IPv4address}
hostname	({domainlabel}".")*{toplabel}(".")? 
domainlabel	{alphanum}|{alphanum}({alphanum}|"-"|"_")*{alphanum}
toplabel	{alpha}|{alpha}({alphanum}|"-"|"_")*{alphanum}
IPv4address	{digit}+"."{digit}+"."{digit}+"."{digit}+
port		{digit}*

path		({abs_path}|{opaque_part})?
path_segments	{segment}("/"{segment})*
segment		{param}(";"{param})*
param		{pchar}*
pchar		{unreserved}|{escaped}|[:@&=+$,]

query		{uric}*
query_part	{uric_no_and}*

fragment	{uric}*

uric		{reserved}|{unreserved}|{escaped}
uric_no_and	[;/?:@=+$,]|{unreserved}|{escaped}
reserved 	[;/?:@&=+$,]
unreserved 	{mark}|{alphanum}
mark 		[-_.!~*'()]
escaped		"%"{hex}{hex}
hex 		{digit}|[A-Fa-f]
alphanum 	{alpha}|{digit}
alpha 		{lowalpha}|{upalpha}
lowalpha 	[a-z]
upalpha 	[A-Z]
digit 		[0-9]

delims		[<>#%"] 
unwise		[{}|\^[]`]

%s URI_REFERENCE QUERY FRAGMENT HIER_PART PATH_SEGMENTS 
%s ABS_PATH PATH_SEGMENT 
%s HOST PORT
%s USERINFO

%{
#include <string>
#include <sstream>
#include "uri.h"
#undef YY_MAIN
using std::endl;
using std::istringstream;
int yywrap();
#define YY_SKIP_YYWRAP 
%}

%%

<INITIAL>{scheme}"://"  {
#ifdef _TEST
	cout<<"[scheme://]\t"<<yytext<<endl;
#endif //_TEST
	global_URI->scheme.assign(yytext, yyleng-3);
	BEGIN USERINFO;
}

<INITIAL>{scheme}":"{opaque_part}  {
#ifdef _TEST
	cout<<"[scheme:opaque_part]\t"<<yytext<<endl;
#endif //_TEST
	const char* sep = strchr(yytext, ':');
	global_URI->scheme.assign(yytext, sep-yytext);
	global_URI->opaque_part.assign(sep+1);
	BEGIN FRAGMENT;
}

<INITIAL>{scheme}":/"{param}  {
/*		http:/~xzm/abc.html            */
#ifdef _TEST
	cout<<"[scheme:/segment.str]\t"<<yytext<<endl;
#endif //_TEST
	const char* ptr = strstr(yytext, ":/");
	global_URI->scheme.assign(yytext, ptr - yytext);
	global_URI->path_segments.push_back(segment(ptr+1));
	BEGIN PATH_SEGMENT;
}


<INITIAL>"#"{fragment}		{
#ifdef _TEST
	cout<<"[#fragment]\t"<<yytext<<endl;
#endif //_TEST
	global_URI->fragment.assign(yytext+1, yyleng-1);
	return 0;
}

<INITIAL>"//"	{
#ifdef _TEST
	cout<<"[//]\t"<<yytext<<endl;
#endif //_TEST
	BEGIN USERINFO;
}

<INITIAL>"/"{param}	{
#ifdef _TEST
	cout<<"[/segment]\t"<<yytext<<endl;
#endif //_TEST
	global_URI->path_segments.push_back(segment(yytext));
	BEGIN PATH_SEGMENT;
}

<INITIAL>{param}	{
/*             abc.html             */
#ifdef _TEST
	cout<<"[rel_segment.str]\t"<<yytext<<endl;
#endif //_TEST
	global_URI->path_segments.push_back(segment(yytext));
	BEGIN PATH_SEGMENT;
}

<USERINFO>{userinfo}"@"	{
#ifdef _TEST
	cout<<"[userinfo@]\t"<<yytext<<endl;
#endif //_TEST
	global_URI->userinfo.assign(yytext, yyleng-1);
	BEGIN HOST;
}

<USERINFO>{host} 	{
#ifdef _TEST
	cout<<"[host]\t"<<yytext<<endl;
#endif //_TEST
	global_URI->host.append(yytext, yyleng);
	BEGIN PORT;
}

<HOST>{host}		{
#ifdef _TEST
	cout<<"[host]\t"<<yytext<<endl;
#endif //_TEST
	global_URI->host.append(yytext, yyleng);
	BEGIN PORT;
}

<PORT>":"{port}	{
#ifdef _TEST
	cout<<"[:port]\t"<<yytext<<endl;
#endif //_TEST
	istringstream iss(yytext+1);
	iss>>global_URI->port;
	BEGIN PATH_SEGMENT;
}

<PORT>"/"{param}	{
/* 	... www.pku.edu.cn/index.html    */
#ifdef _TEST
	cout<<"[/segment.str]\t"<<yytext<<endl;
#endif //_TEST
	global_URI->path_segments.push_back(segment(yytext));
	BEGIN PATH_SEGMENT;
}

<PORT><<EOF>> {
	global_URI->path_segments.push_back(segment("/"));
	return 0;
}

<PATH_SEGMENT>"/"{param} 	{
#ifdef _TEST
	cout<<"[/segment.str]\t"<<yytext<<endl;
#endif //_TEST
	
	global_URI->path_segments.push_back(segment(yytext));
	BEGIN PATH_SEGMENT;
}

<PATH_SEGMENT>";"{param} 	{
	if (global_URI->path_segments.empty())
		global_URI->path_segments.push_back(segment(""));
	global_URI->path_segments.back().params.push_back(yytext);
	BEGIN PATH_SEGMENT;
}

<PATH_SEGMENT>"?"{query_part}	{
#ifdef _TEST
	cout<<"[?query]\t"<<yytext<<endl;
#endif //_TEST
	global_URI->query.push_back(yytext);
	BEGIN QUERY;
}

<QUERY>"&"{query_part}	{
	global_URI->query.push_back(yytext);
	BEGIN QUERY;
}

<QUERY>"#"{fragment}		{
#ifdef _TEST
	cout<<"[#fragment]\t"<<yytext<<endl;
#endif //_TEST
	global_URI->fragment.assign(yytext+1);
	return 0;
}

<QUERY><<EOF>>	{
	return 0;
}

<PATH_SEGMENT>"#"{fragment}		{
#ifdef _TEST
	cout<<"[#fragment]\t"<<yytext<<endl;
#endif //_TEST
	global_URI->fragment.assign(yytext+1);
	return 0;
}

<PATH_SEGMENT><<EOF>>		{
#ifdef _TEST
	cout<<"[<<EOF>>]\t"<<yytext<<endl;
#endif //_TEST
	if (global_URI->path_segments.empty())
		global_URI->path_segments.push_back(segment("/"));
	return 0;
}

.|\n		{
#ifdef _TEST
	cout<<"[Unknown char]\t"<<yytext<<endl;
#endif //_TEST
	return -1;
}

%%

CURI::CURI() : port(0)
{
}


/*************************************************************************
 @ The following method 
	normalize();
	normalize_escaped();
	toabs();
   is according to 
	http://www.gbiv.com
	/protocols/uri/rev-2002/draft-fielding-uri-rfc2396bis-01.html
*************************************************************************/
void
CURI::normalize()
{
	unsigned i;
	// Case Normalization
	for (i=0; i<scheme.size(); i++)
		scheme[i] = tolower(scheme[i]);
	for (i=0; i<host.size(); i++)
		host[i] = tolower(host[i]);
	// Escape Normalization
	normalize_escaped(scheme);
	normalize_escaped(userinfo);
	normalize_escaped(host);
	normalize_escaped(opaque_part);
	list<segment>::iterator iter;
	for (iter = path_segments.begin()
		; iter != path_segments.end()
		; iter++)
	{
		normalize_escaped(iter->str);
		for (unsigned i=0; i<iter->params.size(); i++)
			normalize_escaped(iter->params[i]);
	}
	for (unsigned i=0; i<query.size(); i++)
		normalize_escaped(query[i]);
	normalize_escaped(fragment);
	// Path Segment Normalization
	
	for (iter = path_segments.begin()
		; iter != path_segments.end()
		; /* iter++ */)
	{
		string &seg = iter->str;
		/* skip relative path */
		if (seg[0] != '/')
			break;   
		if (seg == "/" || seg == "/.")
		{
			seg = "/";
			list<segment>::iterator iter_next = iter;
			iter_next ++;
			if (iter_next != path_segments.end())
				/* http://www.pku.edu.cn/xzm(/.)/index.html */
				path_segments.erase(iter);
			iter = iter_next;
			continue;
		}
		if (seg == "/..")
		{
			list<segment>::iterator iter_prev = iter;
			iter_prev--;
			path_segments.erase(iter++);
			if (iter_prev != path_segments.end())
			{/*      /abc/../images/bg.gif       */
				path_segments.erase(iter_prev);
			}
			/*      /../images/bg.gif     */
			continue;
		}
		iter++;
	}
	if (path_segments.empty())
	{
		path_segments.push_back(segment("/"));
	}
	// Scheme-based Normalization
	if (port == 0)
	{
		port = default_port(scheme);
	}
}

int
CURI::default_port(const string &scheme)
{
	if (scheme == "http")
		return 80;
	else if (scheme == "ftp")
		return 21;
	return 0;
}

ostream& 
CURI::explain(ostream &os)
{
	if (!scheme.empty())
		os<<"scheme:"<<scheme<<'\n';
	if (!userinfo.empty())
		os<<"userinfo:"<<userinfo<<'\n';
	if (!host.empty())
		os<<"host:"<<host<<'\n';
	if (port != default_port(scheme))
		os<<"port:"<<port<<'\n';
	if (!opaque_part.empty())
		os<<"opaque_part:"<<opaque_part<<'\n';
	if (!path_segments.empty())
	{
		os<<"path_segments:"<<'\n';
		list<segment>::const_iterator citer;
		for (citer=path_segments.begin(); citer!=path_segments.end(); citer++)
		{
			os<<'\t'<<citer->str<<'\n';
			for (unsigned i=0; i<citer->params.size(); i++)
				os<<"\t\t"<<citer->params[i]<<'\n';
		}
	}
	if (!query.empty())
	{
		os<<"query:"<<'\n';
		for (unsigned i=0; i<query.size(); i++)
			os<<"\t"<<query[i]<<'\n';
	}
	if (!fragment.empty())
		os<<"fragment:"<<fragment<<'\n';
	os<<std::flush;
	return os;
}

string
CURI::local_ext() const
{
	list<segment>::const_reverse_iterator crit = path_segments.rbegin();  
	if (crit == path_segments.rend())
		return "";
	const string &filename = crit->str;
	string::size_type dot = filename.rfind('.');
	if (dot == string::npos)
		return "";
	return string(filename, dot+1);
}

void 
CURI::normalize_escaped(string &str)
{
	unsigned i;
	for (i=0; i<str.size(); i++)
	{
		if (str[i]=='%' && isxdigit(str[i+1]) && isxdigit(str[i+2]))
		{
			char ch=0;
			char ch1 = toupper(str[i+1]); 
			char ch2 = toupper(str[i+2]);	
			if (isdigit(ch1))
			{
				ch=ch1 - '0';
			}
			else 
			{
				ch=ch1 - 'A' + 10;
			}
			ch *= 16;
			if (isdigit(ch2))
			{
				ch += ch2 -'0';
			}
			else
			{
				ch += ch2 - 'A' + 10;
			}
			if (isalnum(ch) || ch=='~' || ch=='_')
			{
				str[i] = ch;
				str.erase(i+1, 2);	
			}
			else 
			{
				str[i+1] = ch1;
				str[i+2] = ch2;
				i += 2;
			}
		} 
	}
	return;
}

int
CURI::parse(const string &uristr)
{
	path_segments.clear();
	host.clear();
	scheme.clear();
	userinfo.clear();
	query.clear();
	fragment.clear();
	port = 0;
	opaque_part.clear();
	istringstream mem_buf(uristr);
	yyFlexLexer parser(&mem_buf);
	global_URI = this;
	return parser.yylex();
}

void
CURI::toabs(const CURI &base)
{
	if (!scheme.empty())
		return;
	scheme = base.scheme;
	if (host.empty())
		host = base.host;
	else 
		return;
	if (userinfo.empty())
		userinfo = base.userinfo;
	if (port == 0)
		port = base.port;
	if (path_segments.empty())
		path_segments = base.path_segments;
	else if ((path_segments.begin())->str[0] != '/')
	{
		path_segments.begin()->str.insert(0, "/");
		path_segments.insert(path_segments.begin() 
			, base.path_segments.begin()
			, --base.path_segments.end()
			);
	}
	return;
}

int
yywrap()
{
	return 255;
}

#if YY_FLEX_SUBMINOR_VERSION > 34
// in Flex 2.5.35, there is a "virtual int yyFlexLexer::yywrap();" declared.
int
yyFlexLexer::yywrap()
{
	return 255;
}
#endif

static CURI __global_URI;
CURI *global_URI = &__global_URI;

