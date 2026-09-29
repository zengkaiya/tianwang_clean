#ifndef _PAT_MEMORY_HPP_11062009
#define _PAT_MEMORY_HPP_11062009
#include <vector>
using std::vector;

template<class _Tp>
void myFree(_Tp* ptr)
{
	free(ptr);
}

template <class _Tp, void (*fnFree)(_Tp*)>
class scoped_ptr4c
{
public:
    typedef _Tp element_type;
    explicit scoped_ptr4c(_Tp * p = 0): ptr(p) // never throws
    {
    }
	~scoped_ptr4c()
	{
		if (ptr != 0)
			fnFree(ptr);	
	}
	void reset(element_type*  p=0)
	{
		if (p == ptr)
			return;
		if (ptr != 0)
			fnFree(ptr);
		ptr = p;
		return;
	}
	
	element_type* release()
	{
		element_type* ret = ptr;
		ptr = 0;
		return ret;
	}

	element_type& 
	operator*() const throw()
	{
		return *ptr;
	}
	
	element_type*
	operator->() const throw()
	{
		return ptr;
	}
	
    operator bool () const
    {
        return ptr != 0;
    }

    bool operator! () const // never throws
    {
        return ptr == 0;
    }
    
    void swap(scoped_ptr4c & b) // never throws
    {
        element_type * tmp = b.ptr;
        b.ptr = ptr;
        ptr = tmp;
    }

	element_type* get() const
	{
		return ptr;
	}
	element_type& operator[](size_t i)
	{
		return ptr[i];
	}

private:
	element_type* ptr;

    scoped_ptr4c(scoped_ptr4c const &);
    scoped_ptr4c & operator=(scoped_ptr4c const &);
};

template <class _Tp, void (*fnFree)(_Tp*)>
class vector_ptr4c: public vector<_Tp*>
{
public:
	virtual ~vector_ptr4c()
	{
		for (typename vector<_Tp*>::size_type i=0; i<this->size(); i++)
		{
			_Tp* ptr = this->operator[](i);
			if (ptr != 0)
				fnFree(ptr);
		}
	}
private:

};

#endif //_PAT_MEMORY_HPP_11062009
