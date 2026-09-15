obj-m += decnet_iv.o
decnet_iv-y := decnet_iv_main.o decnet_iv_ethernet.o
ccflags-y += -I$(src)/../../include/uapi -I$(src)/../../include

KDIR ?= /lib/modules/$(shell uname -r)/build

.PHONY: all clean
all:
	$(MAKE) -C $(KDIR) M=$(CURDIR) modules

clean:
	$(MAKE) -C $(KDIR) M=$(CURDIR) clean
