CC ?= cc
CPPFLAGS ?= -I../../include/uapi
CFLAGS ?= -O2 -Wall -Wextra -Werror

.PHONY: all check clean
all: dncopy check

dncopy: dncopy.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $<

check: dncopy
	./dncopy --selftest

clean:
	rm -f dncopy
