# Tetra Command

A clock, system stats, a macro pad and settings on the Mobile Pixels Tetra's
8 inch touch panel. Based upon MicroPython and PicoVector, and heavily inspired by/leaning on the Badgeware Tufty2350 app [statsbadge](https://pimoroni.github.io/statsbadge).

## Build

macOS, SDL3, and the two submodules.

```
git clone --recurse-submodules https://github.com/Gadgetoid/tetra-command
brew install sdl3

make embed     # once, and again after any mpconfigport.h change
make
make run
```

`make bundle` builds `TetraCommand.app`. Run it that way for the macro pad and
the weather: a bundle owns its own Accessibility grant, and Location Services
is refused to a bare binary.

## Run

```
./tetra-command                     # covers the display named TETRA
./tetra-command --windowed --size=640x400
./tetra-command --list-displays
```

| Flag | Meaning |
|------|---------|
| `--display=NAME` | substring match on the display name (default `TETRA`) |
| `--root=DIR` | directory mounted as `/` inside MicroPython |
| `--data=DIR` | directory mounted as `/data`, where everything writable lives |
| `--app=FILE` | entry point within root (default `app.py`) |
| `--size=WxH` | override render size |
| `--windowed` | a plain window instead of covering the display |
| `--no-tools` | do not run the sampler and weather fetch as children |
| `--list-displays` | print displays and exit |

Escape or Ctrl-C quits.

## Licence

MIT, see [LICENSE](LICENSE). The fonts keep their own, in
[licences/](licences/).
