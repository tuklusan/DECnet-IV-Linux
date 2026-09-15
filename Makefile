.PHONY: all userspace unit kernel clean

all: userspace unit

userspace:
	$(MAKE) -C userspace/dnctl

unit:
	$(MAKE) -C tests/unit test

kernel:
	$(MAKE) -C kernel/decnet KDIR="$(KDIR)"

clean:
	$(MAKE) -C userspace/dnctl clean
	$(MAKE) -C tests/unit clean
	@if [ -n "$(KDIR)" ]; then $(MAKE) -C kernel/decnet KDIR="$(KDIR)" clean; fi
