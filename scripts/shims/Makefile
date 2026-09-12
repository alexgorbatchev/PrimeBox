# Build ARM32 soft-float translation shims for running rbp on Prime GO.
# Target: ARMv5t / ARM32 soft-float EABI5 (matches RX3 glibc 2.13 userland).
#
# Requires:
#   arm-linux-gnueabi-gcc (from libc6-dev-armel-cross / gcc-arm-linux-gnueabi)
#   extracted/XDJRX3-rootfs (for RX3 libdl, librt and glibc headers)
#
# Usage:
#   make                                    # build all shims
#   make RX3=/path/to/XDJRX3-rootfs         # specify rootfs path
#   make check                              # verify GLIBC_2.4 symbols & soft-float ABI
#   make clean

CROSS   ?= arm-linux-gnueabi-
CC      := $(CROSS)gcc
STRIP   ?= $(CROSS)strip

RX3     ?= ../../extracted/XDJRX3-rootfs
RX3LIB  := $(RX3)/lib
RX3ULIB := $(RX3)/usr/lib

# RX3 glibc 2.13 predates the modern 64-bit time/off_t transition on 32-bit
# ARM. Modern armel cross headers default to the new ABI, so pin
# both knobs to 32 to keep the generated interposition symbols compatible.
CFLAGS  := -O2 -march=armv5t -mfloat-abi=soft -fno-stack-protector -fPIC \
           -U_FILE_OFFSET_BITS -D_FILE_OFFSET_BITS=32 \
           -U_TIME_BITS -D_TIME_BITS=32 \
           -Wall -Wextra -Wno-unused-parameter
LDFLAGS := -L$(RX3LIB) -L$(RX3ULIB) -Wl,-rpath-link,$(RX3LIB):$(RX3ULIB)

# Shared LD_PRELOAD libraries (soft-float, libc-only NEEDED)
SHARED  := knobshim2.so audioshim.so fbshim-tsc.so gpioshim.so tscshim.so crashcatch.so

# Static ARM helpers (have no soft-float runtime dependency)
STATIC  := seqinject2 udplog

.PHONY: all clean check
all: $(SHARED) $(STATIC)

# knobshim2 needs the ALSA sequencer headers; host headers are fine as the
# structs are ABI-stable. Linked with legacy-scan.c and librt for timing.
knobshim2.so: knobshim2.c legacy-scan.c
	$(CC) $(CFLAGS) -shared -Wl,-z,defs -o $@ $^ -lpthread -lc $(RX3LIB)/librt-2.13.so $(LDFLAGS)

# audioshim must bind dlopen/dlsym to libdl GLIBC_2.4 (the .symver directives
# are in the source); link the RX3 libdl explicitly.
audioshim.so: audioshim.c
	$(CC) $(CFLAGS) -shared -o $@ $< $(RX3LIB)/libdl.so.2 -lc $(LDFLAGS)

# fbshim-tsc uses clock_gettime, link librt explicitly with -Wl,-z,defs.
fbshim-tsc.so: fbshim-tsc.c
	$(CC) $(CFLAGS) -shared -Wl,-z,defs -o $@ $< -lpthread -lc $(RX3LIB)/librt-2.13.so $(LDFLAGS)

gpioshim.so: gpioshim.c
	$(CC) $(CFLAGS) -shared -o $@ $< -lc $(LDFLAGS)

tscshim.so: tscshim.c
	$(CC) $(CFLAGS) -shared -o $@ $< -lc $(LDFLAGS)

crashcatch.so: crashcatch.c
	$(CC) $(CFLAGS) -shared -o $@ $< -lc $(LDFLAGS)

seqinject2: seqinject2.c
	$(CC) -O2 -march=armv5t -mfloat-abi=soft -static -o $@ $<

udplog: udplog.c
	$(CC) -O2 -march=armv5t -mfloat-abi=soft -static -o $@ $<

# Fail the build if any GLIBC version above 2.7 or a hard-float tag sneaks in.
check: $(SHARED)
	@echo "== GLIBC symbol versions =="
	@for f in $(SHARED); do \
		echo "-- $$f"; \
		$(CROSS)readelf -s $$f | grep -o 'GLIBC_[0-9.]*' | sort -u; \
	done
	@echo "== ABI checks (must be empty = soft-float) =="
	@for f in $(SHARED); do \
		$(CROSS)readelf -A $$f | grep -E "Tag_ABI_VFP_args|Tag_FP_arch" || true; \
	done

clean:
	rm -f $(SHARED) $(STATIC) *.o
