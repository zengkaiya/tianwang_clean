#ifndef _PAT_CUTEM_H_022007
class cutem
{
public: 
	cutem(bool copyOldData=false);
	cutem(unsigned size, bool copyOldData=false);
	virtual ~cutem();
	bool enlarge(unsigned size);
	void reserve(unsigned n);
	bool decrease(unsigned size);
	char *ptr()
	{
		return data;
	}
private:
	char* data;
	unsigned size;
	bool copyOldData;
};

int zip(const char* source, int len, cutem &target);
int unzip(const char* source, int len, cutem &target, int in_unzip_len=-1);
#define _PAT_CUTEM_H_022007
#endif // _PAT_CUTEM_H_022007
