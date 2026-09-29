#include "cutem.h"
#include "excep.h"
#include <stdexcept>
#include <zlib.h>
#include <cstring>
#include <sstream>

using std::ostringstream;
using std::runtime_error;

cutem::cutem(bool c): data(0), size(0), copyOldData(c)
{
}

cutem::cutem(unsigned size, bool c): data(0), size(0), copyOldData(c)
{
	if (!enlarge(size))
	{
		ostringstream oss;
		oss<<"Cannot new[] from cutem() where size="
		  <<size;
		throw pat_bad_alloc(oss.str());
	}
}

cutem::~cutem()
{
	if (data != 0)
		delete[] data;
}

bool
cutem::enlarge(unsigned size)
{
	if (size <= this->size)
		return true;
	char* t = new char[size];
	if (t == 0)
		return false;
	if (data != 0)
	{
		if (copyOldData)
			memcpy(t, data, this->size);
		delete[] data;
	}
	data = t;
	this->size = size;
	return true;
}

void 
cutem::reserve(unsigned n)
{
	if (!enlarge(n))
	{
		ostringstream oss;
		oss<<"cutem::reserve(), n="<<n;
		throw pat_bad_alloc(oss.str());
	}
}

bool
cutem::decrease(unsigned size)
{
	if (size >= this->size)
		return true;
	char *t = new char[size];
	if (t == 0)
		return false;
	if (data != 0)
	{
		if (copyOldData)
			memcpy(t, data, size);
		delete[] data;
	}
	this->data = t;
	this->size = size;
	return true;
}

int 
zip(const char* source, int len, cutem &target)
{
	uLongf zip_len = compressBound(len) + 12;
	target.reserve(zip_len);
	if (Z_OK != compress((Bytef*)target.ptr(), &zip_len
	    , (const Bytef*)source, len))
		return -1;
	return zip_len;
}

int 
unzip(const char* source, int len, cutem &target, int in_unzip_len)
{
	uLongf unzip_len;
        if (in_unzip_len >= 0)
		unzip_len = in_unzip_len;
	else
		unzip_len = len * 100 + 100;  //just a guess!
	target.reserve(unzip_len);
	int res;
	while ((res=uncompress((Bytef*)target.ptr(), &unzip_len, (const Bytef*)source, len))
		!= Z_OK)
	{
		if (res==Z_MEM_ERROR)
			throw runtime_error("Z_MEM_ERROR for uncompress()");
		else if (res==Z_DATA_ERROR)
			throw runtime_error("Z_DATA_ERROR for uncompress()");
		else if (res==Z_BUF_ERROR)
		{
			unzip_len *= 10;
			target.reserve(unzip_len);
		}
	}
	return unzip_len;
}
