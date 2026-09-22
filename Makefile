# tetra-command - MicroPython + PicoVector on an external touch panel.
#
#   make embed     regenerate micropython_embed/ (after mpconfigport.h changes)
#   make           build ./tetra-command
#   make run       build and run
#   make icon      redraw icon.icns
#   make bundle    assemble TetraCommand.app, which owns its own permissions

include picovector.mk

PROG      = tetra-command

.DEFAULT_GOAL := $(PROG)
MPY_TOP   = micropython
EMBED_DIR = micropython_embed

BUILD   = build
APP     = TetraCommand.app
# Ad-hoc signing makes the designated requirement a bare cdhash, which moves on
# every rebuild and silently drops the app's permissions with it. Pinning it to
# the identifier keeps them. Weak - anything claiming the identifier matches -
# so anything distributed wants a real identity and no -r.
BUNDLE_ID    = com.gadgetoid.tetra-command
CODESIGN_ID  ?= -
CODESIGN_REQ ?= =designated => identifier "$(BUNDLE_ID)"
RES     = $(APP)/Contents/Resources
VENV    = .venv
ICON    = icon.icns

CFLAGS  += -I. -Isrc -Ilib -I$(EMBED_DIR) -I$(EMBED_DIR)/port -I$(MPY_TOP)
CFLAGS  += -Wall -O2 -fno-common -MMD -MP
CFLAGS  += $(PV_INCLUDES) $(PV_DEFINES)
CFLAGS  += $(shell pkg-config --cflags sdl3)

LDFLAGS += $(shell pkg-config --libs sdl3) $(PV_LDFLAGS) -lc++

CXXFLAGS = $(filter-out -std=c99,$(CFLAGS)) -std=c++17 -Wno-unused-variable

UNAME := $(shell uname -s)
ifeq ($(UNAME),Darwin)
  LDFLAGS += -framework IOKit -framework CoreFoundation -framework ApplicationServices
  LDFLAGS += -framework CoreLocation -framework Foundation -framework Cocoa
  SRC_PLATFORM += src/input/input_hid_macos.c
  SRC_PLATFORM += src/display/ddc_macos.c
  SRC_PLATFORM += src/paths_macos.c
  SRC_OBJC     += src/location_macos.m
  SRC_OBJC     += src/window_macos.m
endif

SRC_APP = \
	src/main.c \
	src/children.c \
	src/display/display_sdl.c \
	src/input/input_queue.c \
	src/runtime/runtime.c \
	src/runtime/mod_host.c \
	src/runtime/mp_shims.c \
	src/runtime/mod_hid.c \
	src/runtime/mod_ddc.c \
	$(SRC_PLATFORM)

# extmod pieces the embed port does not package.
SRC_EXTMOD = $(addprefix $(MPY_TOP)/extmod/, \
	vfs.c vfs_reader.c vfs_posix.c vfs_posix_file.c vfs_blockdev.c modos.c modjson.c)

SRC_EMBED = $(wildcard $(EMBED_DIR)/*/*.c) $(wildcard $(EMBED_DIR)/*/*/*.c)

SRC_C   = $(SRC_APP) $(SRC_EXTMOD) $(SRC_EMBED) $(PV_SRC_C)
SRC_CXX = $(PV_SRC_CXX)

# Objects go under build/, mirroring the source tree. Never beside the sources:
# picovector and its bindings are checkouts we commit to, and stray .o/.opp/.d
# files in them show up as untracked noise in every git status.
OBJ  = $(addprefix $(BUILD)/,$(SRC_C:.c=.o) $(SRC_CXX:.cpp=.opp) $(SRC_OBJC:.m=.om))
DEPS = $(OBJ:.o=.d)
DEPS := $(DEPS:.opp=.d)
DEPS := $(DEPS:.om=.d)

# Binding tables embed qstr *numbers* from this header. If it is regenerated and
# only some objects rebuild, the numbers disagree between translation units and
# you get nonsense attribute lookups, then crashes. Force a full rebuild on it.
GENHDR_QSTR = $(EMBED_DIR)/genhdr/qstrdefs.generated.h

$(BUILD)/%.o: %.c
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -c -o $@ $<

$(BUILD)/%.opp: %.cpp
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) -c -o $@ $<

# ARC, so the location watcher's objects are released without a dealloc here.
$(BUILD)/%.om: %.m
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -fobjc-arc -c -o $@ $<

$(OBJ): $(GENHDR_QSTR)

$(PROG): $(OBJ)
	$(CXX) -o $@ $^ $(LDFLAGS)

-include $(DEPS)

embed:
	$(MAKE) -f micropython_embed.mk

embed-clean:
	rm -rf build-embed $(EMBED_DIR)

run: $(PROG) $(VENV)
	./$(PROG)

# psutil, for the sampler the app runs as a child. Copied into the bundle, so
# the app never has to find an interpreter on a Finder launch's bare PATH.
$(VENV): pyproject.toml
	uv sync
	@touch $(VENV)

venv: $(VENV)

# Stdlib and iconutil only, so this needs no venv.
$(ICON): tools/make_icon.py
	python3 tools/make_icon.py $@

icon: $(ICON)

# Location Services is refused to an unbundled binary, and Accessibility goes to
# whichever terminal launched it; a bundle owns both grants itself. Nothing in
# here is written at runtime: that breaks the seal and takes the grants with it.
bundle: $(PROG) $(VENV) $(ICON) packaging/Info.plist
	rm -rf $(APP)
	mkdir -p $(APP)/Contents/MacOS $(RES)
	cp packaging/Info.plist $(APP)/Contents/Info.plist
	cp $(PROG) $(APP)/Contents/MacOS/$(PROG)
	cp $(ICON) $(RES)/$(ICON)
	cp -R py $(RES)/py
	cp -R tools $(RES)/tools
	cp -R $(VENV) $(RES)/venv
	find $(RES) -name __pycache__ -type d -prune -exec rm -rf {} +
	codesign --force --sign "$(CODESIGN_ID)" -r '$(CODESIGN_REQ)' $(APP)
	@echo "built $(APP)"

clean:
	rm -rf $(BUILD) $(PROG) $(APP)

# mpconfigport.h changes invalidate the generated headers.
rebuild: embed-clean embed clean $(PROG)

.PHONY: embed embed-clean run venv icon bundle clean rebuild
