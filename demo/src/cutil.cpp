#include <cstring>
#include <cctype>
#include <cstdlib>
#include <cstdio>
#include <string>
#include "cutil.h"
using std::string;

const char* 
strncasestr(const char* big, const char* small, unsigned n)
{
	if (big==0 || small==0 || n<=0)
		return 0;
	const char* start = big;
	unsigned len = strlen(small);
	while (start + len <= big + n)
	{
		if (strncasecmp(start, small, len) == 0)
			return start;
		start ++;
	}
	return 0;
}

#ifndef HAVE_STRNSTR
char*
strnstr(const char* big, const char* small, unsigned n)
{
	for (unsigned i=0; i < n && big[i] != '\0'; i++)
	{
		unsigned j;
		for (j=0; small[j] != 0; j++)
		{
			if (big[i+j] != small[j])
				break;
		}
		if (small[j]==0)  // find!
		{
			return (char*)(big+i);
		}
	}
	return 0;
}
#endif //HAVE_STRNSTR

#ifndef HAVE_STRCASESTR
char*
strcasestr(const char* big, const char* small)
{
	for (unsigned i=0; big[i] != '\0'; i++)
	{
		unsigned j;
		for (j=0; small[j] != 0; j++)
		{
			if (tolower(big[i+j]) != tolower(small[j]))
				break;
		}
		if (small[j]==0)  // find!
		{
			return (char*)(big+i);
		}
	}
	return 0;
}
#endif //HAVE_STRCASESTR

#ifndef HAVE_STRNDUP
char* 
strndup(const char* s, size_t n)
{
	char* target = (char*)malloc(n+1);
	if (target==0)
		return 0;
	strncpy(target, s, n);
	target[n] = '\0';
	return target;
}
#endif //HAVE_STRNDUP

#ifndef HAVE_GETLINE 
int 
getline(char** lineptr, size_t *n, FILE *stream)
{
	unsigned len=0;
	if (*lineptr == 0)
	{
		*n = 256;
		if ((*lineptr = (char*)malloc(*n)))
			return -1;
	}
	if (fgets(*lineptr, *n, stream) == 0)
		return -1;
	len = strlen(*lineptr);
	while (len == *n-1 && *lineptr[*n-2] != '\n')
	{
		*n *= 2;
		char* tmp = (char*)realloc(*lineptr, *n);
		if (tmp==0)
			return -1;
		*lineptr = tmp;
		if (fgets(*lineptr+len, *n-len, stream) == 0)
			return -1;
		len = strlen(*lineptr);
	}
	return 0;
}

#endif // HAVE_GETLINE 

#ifndef HAVE_INTOA
char* 
intoa(int value, char* str, size_t n, int base)
{
	if (base != 10)
		return (char*)0;
	int start = 0;
// "-1" is to reserve one byte for the terminating '\0'
	if ( value < 0 && start<(int)n -1 )
	{
		str[start++] = '-';
		value = abs(value);
	}
	int i = start;
	while (i<(int)n-1 && value!=0)
	{
		str[i++] = '0' + value % base;
		value /= base;
	}
	if (value != 0)
		return (char*)0;
	if (i==0)
		str[i++] = '0';
	int end = i--;
	while (start < i)
	{
		char ch;
		ch = str[start];
		str[start] = str[i];
		str[i] = ch;
		i--;
		start++;
	}
	str[end] = '\0';
	return str;
}
#endif //HAVE_INTOA


