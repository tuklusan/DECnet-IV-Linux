CC ?= cc
CPPFLAGS += -I../../include/uapi -I../../include
CFLAGS ?= -O2 -g
CFLAGS += -std=c11 -Wall -Wextra -Werror

.PHONY: all test clean
all: test_uapi test_phase3

test_uapi: test_uapi.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $<

test_phase3: test_phase3.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $<

test: all
	./test_uapi
	./test_phase3

clean:
	rm -f test_uapi test_phase3
