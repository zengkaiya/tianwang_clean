#include "arg.h"
#include <cstring>
#include <stdlib.h>
#include <cassert>
using std::strlen;
using std::strncmp;

CArg::CArg(int argc, char** argv)
{
    for (int i=0; i<argc; i++)
    {
        this->argv.push_back(argv[i]);
    }
}

CArg::~CArg()
{
}

vector<string>
CArg::follow(const char* option) const
{
    assert(option != (void*)0);
    assert(option[0] == '-');
    vector<string> res;
    int pos;
    for (pos=1; pos<argv.size(); pos++)
    {
        if (argv[pos] == string(option))
            break;
    }
    for (pos++; pos<argv.size(); pos++)
    {
        if (argv[pos][0] == '-')
            break;
        res.push_back(argv[pos]);
    }
    return res;
}

vector<string>
CArg::find(const char* prefix) const
{
    assert(prefix != (void*)0);
    assert(prefix[0] == '-');
    int prefix_len = strlen(prefix);
    vector<string> res;
    for (int i=1; i<argv.size(); i++)
    {
        if (argv[i].substr(0, prefix_len) == string(prefix))
            res.push_back(argv[i].substr(prefix_len));
    }
    return res;
}
