CC ?= cc
CPPFLAGS += -I../../include/uapi
CFLAGS ?= -O2 -g
CFLAGS += -std=c11 -Wall -Wextra -Werror

.PHONY: all test clean
all: test_uapi

test_uapi: test_uapi.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $<

test: test_uapi
	./test_uapi
	python3 test_paranoid_review_gate.py
	python3 test_project_state_gate.py

clean:
	rm -f test_uapi
