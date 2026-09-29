LIBS = -lz
tw_raw_t : tw_raw_t.cpp tw_raw.cpp util.cpp arg.cpp cutem.cpp uri.cc url.cpp \
     http_reply.cpp http_bits.cpp ext.cpp
	g++ -o $@ $^ $(LIBS)
	mkdir -p ../bin
	cp $@ ../bin/
tw_urls_t : tw_urls_t.cpp tw_raw.cpp util.cpp arg.cpp cutem.cpp uri.cc url.cpp \
     http_reply.cpp http_bits.cpp ext.cpp
	g++ -o $@ $^ $(LIBS)
	mkdir -p ../bin
	cp $@ ../bin/
tw_export_samples_t : tw_export_samples_t.cpp tw_raw.cpp util.cpp arg.cpp cutem.cpp uri.cc url.cpp \
     http_reply.cpp http_bits.cpp ext.cpp
	g++ -o $@ $^ $(LIBS)
	mkdir -p ../bin
	cp $@ ../bin/
clean :
	rm -f *.o tw_raw_t tw_urls_t tw_export_samples_t
