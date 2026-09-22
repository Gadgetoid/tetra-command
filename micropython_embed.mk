MICROPYTHON_TOP = micropython

include picovector.mk

# Our own sources that declare qstrs or register modules must be scanned.
SRC_QSTR += src/runtime/mod_host.c src/runtime/mod_hid.c src/runtime/mod_ddc.c

# VFS lives in extmod/, which the embed port does not package by default.
SRC_QSTR += $(addprefix $(MICROPYTHON_TOP)/extmod/, \
	vfs.c vfs_reader.c vfs_posix.c vfs_posix_file.c vfs_blockdev.c modos.c modjson.c)

# The bindings are C++; makeqstrdefs preprocesses .cpp with QSTR_GEN_CXXFLAGS,
# which mkrules derives from CXXFLAGS.
SRC_QSTR += $(PV_QSTR_SRC)

CFLAGS   += $(shell pkg-config --cflags freetype2) -I$(CURDIR) -I$(CURDIR)/src -I$(CURDIR)/$(MICROPYTHON_TOP) $(PV_INCLUDES) $(PV_DEFINES)
CXXFLAGS += -std=c++17

include $(MICROPYTHON_TOP)/ports/embed/embed.mk
