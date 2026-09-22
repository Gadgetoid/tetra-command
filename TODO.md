# TODO

## Outstanding

- **Do something with pico3d.** It builds and imports now (engine, light, mat4,
  material, mesh, surface, vec3) and nothing uses it. A rotating something on a
  page is the obvious first thing.
- **Material Symbols is 10.6MB** for about forty glyphs, which is most of the
  repo. Subsetting wants verifying glyph by glyph, so it was left whole.
- **Cheap pages from ported code.** `draw.bars` is in and unused: per-core CPU
  is nearly free off `cpu.cores`, and a memory page off `mem.*`.
- **GPU page.** Dropped for now; needs the `powermetrics` sudoers rule, and
  then a source for die temp, fan RPM and package power.
- **Nowhere to set a place by hand.** `--auto` covers the normal case, but a
  denied grant, or wanting the weather somewhere else, means an argument to
  `fetch_weather.py`. A settings page writing the place into config.json, which
  `--auto` would prefer over the fix, is the missing half.
- **No on-screen sign that Accessibility is missing.** `hid.ready()` asks for it
  now, but if the prompt is dismissed the macro pad is just dead keys. The page
  should say so rather than leaving it to a `print` nothing can see.
- **Field icons beyond the disk page.** `cpu`, `net` and `load` draw readouts
  and graphs, neither of which takes an icon. statsbadge's `FIELD_ICONS` covers
  those fields already if the widgets ever want them.
