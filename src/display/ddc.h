// The panel's own OSD controls, driven from the host over DDC/CI.
#pragma once
#include <stdbool.h>
#include <stdint.h>

#include "host.h"

// MCCS codes this panel actually implements, found by scanning 0x00-0xff and
// keeping the ones whose reply carries a success result byte (probes/ddcscan.c).
// Two absences worth knowing: saturation (0x8a) reports unsupported even though
// the OSD offers it, and sharpness (0x87) answers reads and writes but changes
// nothing on screen. Eye care mode and the underglow are not reachable at all.
#define DDC_BRIGHTNESS      0x10
#define DDC_CONTRAST        0x12
#define DDC_COLOUR_PRESET   0x14
#define DDC_GAIN_RED        0x16
#define DDC_GAIN_GREEN      0x18
#define DDC_GAIN_BLUE       0x1a
#define DDC_INPUT_SOURCE    0x60
#define DDC_BLACK_RED       0x6c
#define DDC_BLACK_GREEN     0x6e
#define DDC_BLACK_BLUE      0x70
#define DDC_POWER_MODE      0xd6

bool ddc_init(const macropad_config_t *cfg);
void ddc_deinit(void);
bool ddc_available(void);

// Answered from cache once a code has been seen. The first read of a code goes
// to the bus and blocks for up to ~150ms, so prime anything the UI draws every
// frame during startup rather than mid-gesture.
bool ddc_get(uint8_t vcp, int *current, int *maximum);

// Queued, never blocking. One pending value per code, latest wins, so dragging
// a slider at 60fps collapses to as many writes as the bus can actually carry.
void ddc_set(uint8_t vcp, int value);
