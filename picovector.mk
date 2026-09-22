# PicoVector: core C++ library + generated MicroPython bindings.
# Mirrors picovector-micropython.cmake and picovector/picovector.cmake, which
# remain the source of truth for the source lists and build knobs.

PV_MP_DIR   = picovector-micropython
PV_DIR      = $(PV_MP_DIR)/picovector
PNGDEC_DIR  = $(PV_DIR)/lib/pngdec
JPEGDEC_DIR = $(PV_DIR)/lib/jpegdec

PV_INCLUDES = \
	-I$(PV_MP_DIR) \
	-I$(PV_MP_DIR)/generated \
	-I$(PV_MP_DIR)/runtime \
	-I$(PV_DIR) \
	-I$(PNGDEC_DIR) \
	-I$(JPEGDEC_DIR)

# The rasteriser-only default working buffer is 60K; PNGDEC/JPEGDEC decode state
# needs it larger. Matches picovector-micropython.cmake.
PV_DEFINES = -DPV_WORKING_BUFFER_SIZE=81920

# Real TTF/OTF via FreeType. Host-class only; embedded builds keep .af.
PV_FREETYPE ?= 1
ifeq ($(PV_FREETYPE),1)
  PV_DEFINES  += -DPV_FREETYPE=1
  # Finely flattened TTF contours run well past the 512-point default.
  PV_DEFINES  += -DPV_GLYPH_POINT_BUF=4096
  PV_INCLUDES += $(shell pkg-config --cflags freetype2)
  PV_LDFLAGS  += $(shell pkg-config --libs freetype2)
endif

# 3D, which picovector_micropython.cmake gates behind PV_PICO3D. The bindings
# come from a wildcard here, so the define has to agree or pv_bindings.hpp
# guards the module out while its sources still build.
PV_PICO3D ?= 1
ifeq ($(PV_PICO3D),1)
  PV_DEFINES += -DPV_PICO3D=1
endif

# The same set the cmake lists under PV_PICO3D, for filtering it back out.
PV_3D_SRC = $(addprefix $(PV_MP_DIR)/, \
	generated/pico3d_bindings.c generated/vec3.cpp generated/mat4.cpp \
	generated/mesh.cpp generated/material.cpp generated/light.cpp \
	generated/surface.cpp generated/engine.cpp native/pico3d_native.cpp)

# Core library. PICO3D_RASTER=int_templated, as picovector.cmake selects.
PV_CORE_CXX = \
	$(PV_DIR)/picovector.cpp $(PV_DIR)/rasteriser.cpp \
	$(PV_DIR)/picovector_working_buffer.cpp $(PV_DIR)/shape.cpp \
	$(PV_DIR)/font.cpp $(PV_DIR)/font_parse.cpp $(PV_DIR)/gif_parse.cpp \
	$(PV_DIR)/pixel_font.cpp $(PV_DIR)/image.cpp $(PV_DIR)/blit.cpp \
	$(PV_DIR)/brush.cpp $(PV_DIR)/color.cpp $(PV_DIR)/primitive.cpp \
	$(PV_DIR)/pico3d_raster_int_templated.cpp $(PV_DIR)/pico3d_draw.cpp \
	$(PV_DIR)/algorithms/geometry.cpp $(PV_DIR)/algorithms/dda.cpp \
	$(PV_DIR)/tween/easing.cpp $(PV_DIR)/tween/tween.cpp \
	$(wildcard $(PV_DIR)/brushes/*.cpp) \
	$(wildcard $(PV_DIR)/filters/*.cpp)

PV_CORE_C = $(PV_DIR)/lib/qrcodegen/qrcodegen.c

# Bindings: generated + hand-written bodies + shared glue.
PV_BIND_C   = $(wildcard $(PV_MP_DIR)/generated/*.c)
PV_BIND_CXX = \
	$(wildcard $(PV_MP_DIR)/generated/*.cpp) \
	$(wildcard $(PV_MP_DIR)/native/*.cpp) \
	$(PV_MP_DIR)/runtime/pv_support.cpp \
	$(PV_MP_DIR)/runtime/pv_metrics.cpp \
	$(if $(filter 1,$(PV_FREETYPE)),$(PV_MP_DIR)/native/font_freetype.cpp)

ifneq ($(PV_PICO3D),1)
  PV_BIND_C   := $(filter-out $(PV_3D_SRC),$(PV_BIND_C))
  PV_BIND_CXX := $(filter-out $(PV_3D_SRC),$(PV_BIND_CXX))
endif

PNGDEC_SRC  = $(PNGDEC_DIR)/PNGdec.cpp $(PNGDEC_DIR)/adler32.c $(PNGDEC_DIR)/crc32.c \
	$(PNGDEC_DIR)/infback.c $(PNGDEC_DIR)/inffast.c $(PNGDEC_DIR)/inflate.c \
	$(PNGDEC_DIR)/inftrees.c $(PNGDEC_DIR)/zutil.c
JPEGDEC_SRC = $(JPEGDEC_DIR)/JPEGDEC.cpp

# Everything the qstr scanner must see (MP_QSTR_ / MP_REGISTER_MODULE).
PV_QSTR_SRC = $(PV_BIND_C) $(PV_BIND_CXX)

PV_SRC_C   = $(PV_CORE_C) $(PV_BIND_C) $(filter %.c,$(PNGDEC_SRC))
PV_SRC_CXX = $(PV_CORE_CXX) $(PV_BIND_CXX) $(filter %.cpp,$(PNGDEC_SRC)) $(JPEGDEC_SRC)
