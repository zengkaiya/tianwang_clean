#include "tw_raw.h"
#include "arg.h"
#include "./util.h"
#include "http_reply.h"
#include "url.h"
#include <iostream>
#include <sstream>
#include <set>

using namespace std;
ostream&
help(ostream &os)
{
    os<<"Tool for reading CTW_Raw pages and output them.\n"
      "\tUsage: cmd [--prefix=...]* [--select=...] [--num=...] \n"
      "\t\t  [--one-by-one | --package] \n"
      "\t\t  [--http-reply | --body-only] [-h|--help]\n"
      "\t\t--prefix= : select urls with such prefix.\n"
      "\t\t--select= : filename of selected url.\n"
      "\t\t--num= : output num pages at most.\n"
      "\t\t--one-by-one : Write output to seperated files with names:\n"
      "\t\t\t\t \"1.\", \"2.\", \"3.\", ...\n"
      "\t\t\t\t extention will be raw, html, or reply\n"
      "\t\t--package : output record in package:\"http-length\\n http-body\\n\"\n"
      "\t\t--http-reply : output is in http-reply format, tw_raw headers are discarded.\n"
      "\t\t--body-only : only http body is output.\n"
      "\t\t-h|--help : print this message.\n"
      "\t\tcin : CTWRaw pages.\n"
      "\t\tcout : output if \"--one-by-one\" option is not set.\n"
      <<endl;
    return os;
}

int
main(int argc, char* argv[])
{
    CArg arg(argc, argv);
    if (arg.found("-h") || arg.found("--help"))
    {
        help(cout);
        return 1;
    }
    vector<string> prefixes = arg.find("--prefix=");
    string fn;
    set<string> selects;
    if (arg.findLast("--select=", fn))
    {
        ifstream ifs(fn.c_str());
        if (!ifs)
        {
            cerr<<"Can not open select file:\""<<fn<<"\"."<<endl;
            return -6;
        }
        string urlstr;
        while (ifs>>urlstr)
            selects.insert(urlstr);
    }
    int num=0;
    string strNum;
    if (arg.findLast("--num=", strNum))
        num = stoi(strNum);
    bool oneByOne = arg.found("--one-by-one");
    bool body_only = arg.found("--body-only");
    bool http_reply = arg.found("--http-reply");
    bool package = arg.found("--package");
    if (package && oneByOne)
    {
        cerr<<"options \"--one-by-one\", \"--package\" is conflict with each other"
          <<endl;
        return -1;
    }
    CTWRaw raw;
    for (unsigned nloop=0, i=0; (num<=0 || (int)i<num) && cin>>raw; nloop++)
    {
        if (prefixes.size() > 0 || selects.size() > 0)
        {
            bool match = false;
            for (size_t i=0; i<prefixes.size(); i++)
            {
                if (raw.url.compare(0, prefixes[i].length(), prefixes[i]) == 0)
                {
                    match = true;
                    break;
                }
            }
            if (!match && selects.find(raw.url)==selects.end())
                continue;
        }
        i++;

        ostream os(cout.rdbuf());
        ofstream ofs;
        if (oneByOne)
        {
            if (body_only)
            {
                string ext = raw.reply.headers.ext();
                if (ext.empty())
                    ext = CURL(raw.url).local_ext();
                if (ext.empty())
                    ext = "html";
                ofs.open((to_string(i)+"."+ext).c_str());
            }
            else if (http_reply)
                ofs.open((to_string(i)+".reply").c_str());
            else
                ofs.open((to_string(i)+".raw").c_str());
               os.rdbuf(ofs.rdbuf());
        }
        if (package)
        {
            if (body_only)
            {
                os<<raw.reply.body.length()<<'\n'
                   <<raw.reply.body<<endl;
                continue;
            }
            ostringstream oss;
            if (http_reply)
                oss<<raw.reply;
            else
                oss<<raw;
            os<<oss.str().length()<<'\n'<<oss.str()<<endl;
            continue;
        }
        if (body_only)
            os<<raw.reply.body<<endl;
        else if (http_reply)
            os<<raw.reply<<endl;
        else
            os<<raw<<endl;
    }
    return 0;
}
