CC ?= cc
CPPFLAGS += -I../../include/uapi
CFLAGS ?= -O2 -g
CFLAGS += -std=c11 -Wall -Wextra -Werror

.PHONY: all clean
all: dnctl

dnctl: dnctl.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $<

clean:
	rm -f dnctl
