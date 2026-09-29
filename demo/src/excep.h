#ifndef _PAT_EXCEP_H_050603
#define _PAT_EXCEP_H_050603
#include <stdexcept>
#include <string>


class pat_bad_alloc : public std::bad_alloc
{
public:
	pat_bad_alloc(const std::string& m) : _M_msg(m)
	{}
	virtual ~pat_bad_alloc() throw ()
	{}
private:
	std::string _M_msg;
};
#endif /* _PAT_EXCEP_H_050603 */
