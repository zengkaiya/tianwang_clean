#ifndef _PAT_ARG_H_100603_
#define _PAT_ARG_H_100603_
#include <vector>
#include <string>
using std::string;
using std::vector;

class CArg 
{
public:
	CArg(int argc, char** argv);
	virtual ~CArg();
	vector<string> find(const char* prefix) const;
	vector<string> follow(const char* option) const;
        bool findLast(const char* prefix, string &last) const
        {
            vector<string> val = find(prefix);
            if (val.size() > 0)
            {
                last = val.back();
                return true;
            }
            return false;
        }
    bool findLastInt(const char* prefix, int &num) const
    {
        string strNum;
        if (findLast(prefix, strNum))
        {
            num = stoi(strNum);
            return true;
        }
        return false;
    }
        bool found(const char* prefix) const
        {
            return find(prefix).size() > 0;
        }
private:
	vector<string> argv;
};

#endif // _PAT_ARG_H_100603_
