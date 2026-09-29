#ifndef _PAT_CUTIL_H_01022004_
#define _PAT_CUTIL_H_01022004_
#include <cstdio>
#include <string>
#include "config.h"
using std::string;
/*
 * Instead of "const char*", we return "char*" here to be consistent with 
 * the standard version of strnstr, strcasestr, etc.
 */
#ifndef HAVE_STRNSTR
char* strnstr(const char* big, const char* small, unsigned n);
#endif // HAVE_STRNSTR

#ifndef HAVE_STRCASESTR
char* strcasestr(const char* big, const char* small);
#endif // HAVE_STRCASESTR

const char* strncasestr(const char* big, const char* small, unsigned n);

#ifndef HAVE_STRNDUP
char* strndup(const char* s, size_t n);
#endif

#ifndef HAVE_GETLINE
int getline(char **lineptr, size_t *n, FILE *stream);
#endif 

#ifndef HAVE_INTOA
char* intoa(int value, char* str, size_t n, int base=10);
#endif 

#endif // _PAT_CUTIL_H_01022004_
