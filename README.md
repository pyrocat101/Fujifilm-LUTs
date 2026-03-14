# Fujifilm Film Simulation LUTs & Creative Profiles

3D LUTs and **ACR/Lightroom Creative Profiles** that apply Fujifilm's official
film simulation looks to images in **ACES** (ACEScct / ACES2065-1),
**ProPhoto RGB**, **Apple Log**, and **Adobe Camera Raw / Lightroom**.

Generated from the official Fujifilm F-Log2C / F-Gamut C LUTs
(GFX ETERNA 55, V1.00) using the color science from Fujifilm's published
IDT and F-Log2C data sheet.

## Available Film Simulations

| LUT name | Description |
|----------|-------------|
| PROVIA | Standard color and contrast |
| Velvia | Vivid color, high contrast |
| ASTIA | Soft tone, natural skin |
| CLASSIC CHROME | Muted color, documentary feel |
| CLASSIC Neg. | High-contrast with unique color rendering |
| REALA ACE | Natural color reproduction |
| PRO Neg.Std | Soft color, portrait-oriented |
| ETERNA | Cinema, subdued color and contrast |
| ETERNA BB | Bleach bypass, desaturated high-contrast |
| ACROS | Monochrome with fine grain tonality |

## Output Structure

```
output/
  ACR_profiles/             # ACR / Lightroom Creative Profiles (.xmp)
    Fujifilm PROVIA.xmp
    ...

  ProPhoto/                 # ProPhoto RGB (gamma 1.8) -> ProPhoto RGB (gamma 1.8)
    ProPhoto_to_PROVIA_65grid.cube
    ProPhoto_to_PROVIA_33grid.cube
    ...

  ACEScct_display/          # ACEScct (AP1, log) -> BT.709 / Gamma 2.2
    ACEScct_to_PROVIA_65grid.cube
    ACEScct_to_PROVIA_33grid.cube
    ...

  AP0_display/              # Linear ACES2065-1 (AP0) -> BT.709 / Gamma 2.2
    AP0_to_PROVIA_65grid.cube
    AP0_to_PROVIA_33grid.cube
    ...

  AppleLog_display/         # Apple Log (BT.2020) -> BT.709 / Gamma 2.2
    AppleLog_to_PROVIA_65grid.cube
    AppleLog_to_PROVIA_33grid.cube
    ...

  AppleLog2_display/        # Apple Log 2 (Apple Gamut) -> BT.709 / Gamma 2.2
    AppleLog2_to_PROVIA_65grid.cube
    AppleLog2_to_PROVIA_33grid.cube
    ...
```

Each film simulation is available in both **65-grid** (higher precision) and **33-grid**
(wider compatibility, e.g. Kino Pro) `.cube` files with input domain [0, 1].

### What each variant does

**ACR Creative Profiles** are `.xmp` files that appear in Lightroom / Camera Raw's
profile browser under the "Fujifilm" group. They embed a 32x32x32 3D LUT and include
the inverse of ACR's default tone curve to avoid double tone mapping, so the Fujifilm
film simulation's own tone curve is the only one applied. A +1 stop exposure offset is
baked in to compensate for the brightness difference between ACR's default S-curve and
the Fujifilm sims' more conservative tone mapping (configurable via
`EXPOSURE_OFFSET_STOPS` in `generate_profiles.py`). The profiles support the Amount
slider (0-200%) and work with all camera models.

**ProPhoto** LUTs are *look LUTs* -- input and output are both ProPhoto RGB with
standard gamma 1.8 encoding (the built-in Photoshop `ProPhoto RGB` profile).
The film simulation look is baked in, with all output colors within BT.709 gamut.

**ACEScct display** LUTs take ACEScct-encoded input (AP1 primaries, log curve) and
output display-ready BT.709 / Gamma 2.2. They operate directly in DaVinci Resolve's
ACEScct node tree. The log encoding provides excellent shadow precision and covers
~10 stops above 18% gray within the [0, 1] LUT domain.

**AP0 display** LUTs take scene-linear ACES2065-1 (AP0) input and output BT.709 /
Gamma 2.2. This is the universal/archival variant for use in Nuke, custom pipelines,
or any context where linear AP0 is the working space.

**Apple Log display** LUTs take Apple Log input (BT.2020 primaries, as recorded by
iPhone 15 Pro and 16 Pro) and output display-ready BT.709 / Gamma 2.2. Use these as
a display LUT in camera apps or video editors when shooting Apple Log.

**Apple Log 2 display** LUTs take Apple Log 2 input (Apple Gamut primaries, as recorded
by iPhone 17 Pro and later) and output display-ready BT.709 / Gamma 2.2. The transfer
function is identical to Apple Log; only the color primaries differ (Apple Gamut is
wider than BT.2020, particularly in blues and reds).

Both ACES variants **replace** (not supplement) the ACES Output Transform.

---

## Recommended Workflows

### Adobe Camera Raw / Lightroom (Creative Profiles)

1. **Install the profiles**: Copy the `.xmp` files to the Creative Profiles directory:
   - **macOS**: `~/Library/Application Support/Adobe/CameraRaw/Settings/`
   - **Windows**: `%APPDATA%\Adobe\CameraRaw\Settings\`
2. **Restart** Lightroom or Photoshop
3. **Select a profile**: In the Develop module (Lightroom) or Camera Raw, open the
   Profile Browser. The Fujifilm profiles appear under the "Fujifilm" group
4. **Adjust Amount**: Use the Amount slider (0-200%) to control the strength of
   the film simulation look

**Important: Use "Adobe Standard" as your base camera profile.** The profiles bake
the inverse of ACR's default tone curve (the ACR3 S-curve) into the LUT. This
inverse is only correct when the base camera profile uses the default ACR3 curve.
"Adobe Standard" uses this default curve; other profiles ("Adobe Color", "Adobe
Landscape", camera-matching profiles like "Camera PROVIA/Standard") embed their
own `ProfileToneCurve` that replaces the default, so the inverse cancellation
would be imprecise. The Creative Profile format does not support forcing a
specific base profile, so this must be set manually.

**Exposure tuning:** If the profiles look too bright or too dark for your taste,
you can regenerate them with a different exposure offset by changing
`EXPOSURE_OFFSET_STOPS` in `generate_profiles.py` (default: `1.0` stop).
Set to `0.0` for the "pure" Fujifilm rendering (will look ~1 stop darker
than ACR's default).

### Photoshop (ProPhoto RGB)

1. **Develop RAW in Camera Raw** with your preferred Adobe color profile.
   In Camera Raw's output settings (Workflow Options), set Color Space to
   **ProPhoto RGB** (gamma 1.8). This ensures the document pixels are in the
   correct encoding for the LUT. Your Photoshop working space and display
   profile do not matter -- Photoshop uses the document's embedded profile
   for color management, and the LUT operates on the pixel values directly
2. **Apply the LUT** via a Color Lookup adjustment layer:
   Layer > New Adjustment Layer > Color Lookup. In the Properties panel,
   click the "3D LUT File" dropdown and select "Load 3D LUT..." to browse
   for a `ProPhoto_to_*.cube` file
3. **Export to sRGB**: use any of these methods:
   - **File > Export > Export As**: check "Convert to sRGB"
   - **File > Export > Save for Web (Legacy)**: check "Convert to sRGB"
   - **Edit > Convert to Profile**: convert to sRGB, then save normally
     (this changes the document -- undo or close without saving to keep
     working in ProPhoto RGB)

The LUT input and output are both gamma 1.8 ProPhoto RGB. What you see on screen
in Photoshop (through ICC color management) is the intended film simulation appearance.
You can add adjustment layers above or below the LUT for fine-tuning.

**Note on contrast:** The ProPhoto LUTs will produce different contrast than
Adobe Camera Raw's built-in camera-matching profiles (e.g., "Camera PROVIA/Standard").
This is because ACR applies its own tone curve during RAW development, and the
Fujifilm LUT applies another on top — the LUT was designed for flat F-Log2C footage,
not already-developed images. The color rendering will be similar but the contrast
will differ. This is inherent to the approach; see Known Limitations below.

### DaVinci Resolve (ACES)

These LUTs **replace** the ACES Output Transform. Do not stack them with an ODT.

**Setup:**

1. Project Settings > Color Management > Color Science: **ACEScct**
2. Set the **ACES Output Device Transform** to **No Output Transform**
3. In the Color page node tree, add a **Serial Node** (Alt+S) and apply the LUT:
   right-click the node > LUT > choose an `ACEScct_to_*.cube` file

**Why disable the ODT?** The film simulation LUT already includes tone mapping,
gamut mapping, and a display gamma curve -- it is a complete display transform.
Applying the ACES RRT+ODT on top would double-compress highlights and alter contrast.

### DaVinci Resolve (non-ACES)

If you are not using ACES color management but your timeline is in a camera-native
or wide-gamut space, convert to ACEScct first (via a CST node), then apply the
LUT as above.

### Nuke / Custom Pipelines (AP0)

Use the `AP0_display/` LUTs. These expect scene-linear ACES2065-1 (AP0) input and
output display-ready BT.709 / Gamma 2.2. In Nuke, apply via a Vectorfield node.
AP0 is strictly wider than F-Gamut C, so the input gamut conversion is lossless.

### iPhone (Apple Log / Apple Log 2)

These LUTs transform Apple Log footage into Fujifilm film simulation looks.

- **iPhone 15 Pro / 16 Pro** (Apple Log): use the `AppleLog_display/` LUTs
- **iPhone 17 Pro and later** (Apple Log 2): use the `AppleLog2_display/` LUTs

**Blackmagic Camera app:**

1. Import a `*_33grid.cube` file into the app's LUT library (supports 17 and
   33-point LUTs; 65-point is not recommended on iOS)
2. Record in Apple Log while using the LUT for **on-screen monitoring** --
   the flat log footage is recorded to disk while you see the film simulation
   look in the viewfinder
3. Alternatively, bake the LUT into the recording directly

**Kino Pro:**

1. Import a `*_33grid.cube` file into Kino (Settings > Grade > Import). Kino
   accepts LUTs up to 33x33
2. Set the LUT's input color space to "Apple Log" when importing
3. With Instant Grade off, the LUT is a live preview only (monitoring);
   with Instant Grade on, it is baked into the recording

**Post-production:**

Apply the LUT in DaVinci Resolve, Final Cut Pro, Premiere Pro, or any editor
that supports `.cube` files. Ensure your timeline interprets the footage as
Apple Log (BT.2020) before applying the LUT.

### Other Applications

The `.cube` files work in any application that supports 3D LUTs (Premiere Pro,
Final Cut Pro, etc.). Ensure the input matches the expected color space and encoding:

- `ProPhoto/` LUTs: input must be **ProPhoto RGB, gamma 1.8**
- `ACEScct_display/` LUTs: input must be **ACEScct** (AP1 primaries, log encoding)
- `AP0_display/` LUTs: input must be **linear ACES2065-1 (AP0)**
- `AppleLog_display/` LUTs: input must be **Apple Log (BT.2020 primaries)**
- `AppleLog2_display/` LUTs: input must be **Apple Log 2 (Apple Gamut primaries)**

---

## Reproducing the LUTs

### Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python package runner)
- The official Fujifilm F-Log2C 3D LUTs (GFX ETERNA 55, V1.00):
  1. Download from the [Fujifilm LUT download page](https://fujifilm-x.com/en-us/support/download/software/lut/)
     (select "GFX ETERNA 55" under 3D LUT)
  2. Extract the archive so that the 65-grid F-Log2C LUTs are at
     `gfx-eterna-55-3d-lut-v100/65Grid/F-Log2C/` relative to this repo

### Generate

```sh
# Generate .cube LUTs (all variants)
uv run generate_luts.py

# Generate ACR/Lightroom Creative Profiles (.xmp)
uv run generate_profiles.py
```

`generate_luts.py` reads the 10 source film simulation LUTs, computes color space
conversion matrices, and writes 100 output LUTs (50 at 65-grid, 50 at 33-grid)
to `output/`.

`generate_profiles.py` generates 10 Creative Profile `.xmp` files to
`output/ACR_profiles/`. Each profile embeds a 32x32x32 ProPhoto RGB (gamma 1.8)
3D LUT with the inverse ACR3 tone curve baked in.

Both scripts run built-in verification:
- Matrix round-trip and white point preservation
- F-Log2C encoding against Fujifilm's documented reference points
- ACEScct / Apple Log transfer function round-trip and cut point continuity
- Neutral axis comparison between original and generated LUTs
- (Profiles) ACR3 inverse curve validation, base-85 round-trip, XMP/binary
  structure integrity, LUT data reconstruction accuracy

---

## Technical Details

### Conversion Pipeline

Each output LUT/profile bakes the following chain into a single 3D LUT:

```
ACR Creative Profile variant (32-grid .xmp):
  ProPhoto RGB (gamma 1.8) -- as received from ACR's pipeline
    -> [decode gamma 1.8 to linear]
    -> [inverse ACR3 S-curve -- undo ACR's tone mapping]
    -> [+1 stop exposure offset -- match ACR's default brightness]
    -> [matrix: ProPhoto to F-Gamut C, with Bradford D50->D65]
    -> [F-Log2C encoding]
    -> [original Fujifilm 3D LUT lookup]
    -> BT.709 / Gamma 2.2
    -> [decode gamma 2.2 to linear]
    -> [matrix: BT.709 to ProPhoto, with Bradford D65->D50]
    -> [encode gamma 1.8]
    -> ProPhoto RGB (gamma 1.8)

ProPhoto variant:
  ProPhoto RGB (gamma 1.8)
    -> [decode gamma 1.8 to linear]
    -> [matrix: ProPhoto to F-Gamut C, with Bradford D50->D65]
    -> [F-Log2C encoding]
    -> [original Fujifilm 3D LUT lookup]
    -> BT.709 / Gamma 2.2
    -> [decode gamma 2.2 to linear]
    -> [matrix: BT.709 to ProPhoto, with Bradford D65->D50]
    -> [encode gamma 1.8]
    -> ProPhoto RGB (gamma 1.8)

ACEScct display variant:
  ACEScct (AP1, log)
    -> [decode ACEScct to linear]
    -> [matrix: AP1 to F-Gamut C, using official Fujifilm IDT inverse]
    -> [F-Log2C encoding]
    -> [original Fujifilm 3D LUT lookup]
    -> BT.709 / Gamma 2.2 (output directly)

AP0 display variant:
  Linear ACES2065-1 (AP0)
    -> [matrix: AP0 to F-Gamut C, using official Fujifilm IDT inverse]
    -> [F-Log2C encoding]
    -> [original Fujifilm 3D LUT lookup]
    -> BT.709 / Gamma 2.2 (output directly)

Apple Log display variant:
  Apple Log (BT.2020)
    -> [decode Apple Log to linear]
    -> [matrix: BT.2020 to F-Gamut C, computed from primaries (both D65)]
    -> [F-Log2C encoding]
    -> [original Fujifilm 3D LUT lookup]
    -> BT.709 / Gamma 2.2 (output directly)

Apple Log 2 display variant:
  Apple Log 2 (Apple Gamut)
    -> [decode Apple Log to linear (same transfer function)]
    -> [matrix: Apple Gamut to F-Gamut C, computed from primaries (both D65)]
    -> [F-Log2C encoding]
    -> [original Fujifilm 3D LUT lookup]
    -> BT.709 / Gamma 2.2 (output directly)
```

### Color Space Matrices

- **AP0/AP1 to F-Gamut C**: Derived from the official Fujifilm IDT matrix
  (`FUJIFILM_IDT_F-Log2C_Ver.1.00.ctl`) and the standard ACES AP1-to-AP0 matrix
  (S-2014-004). Not computed from primaries + Bradford, since the ACES D60 white
  point produces a discrepancy with generic Bradford adaptation.
- **BT.2020 to F-Gamut C** and **Apple Gamut to F-Gamut C**: Computed from
  primaries (all D65, no chromatic adaptation needed).
- **ProPhoto to F-Gamut C** and **BT.709 to ProPhoto**: Computed from primaries
  with Bradford chromatic adaptation (D50/D65).

### Source Data

- Film simulation LUTs: [Fujifilm GFX ETERNA 55, V1.00](https://fujifilm-x.com/en-us/support/download/software/lut/) (F-Log2C / F-Gamut C)
- F-Log2C transfer function: Fujifilm F-Log2C Data Sheet, Ver.1.0 (included in the LUT download)
- F-Gamut C to ACES matrix: [`FUJIFILM_IDT_F-Log2C_Ver.1.00.ctl`](https://github.com/AcademySoftwareFoundation/OpenACES/blob/main/aces/input/IDT.Fujifilm.F-Log2C_F-GamutC.ctl) (ACES Input Transforms)
- ACEScct transfer function: ACES S-2016-001
- Apple Log / Apple Log 2 transfer function: Apple Log Profile White Paper (Apple Inc., 2023)
- Apple Gamut primaries: [`CSC.Apple.AppleLog2_to_ACES.ctl`](https://github.com/AcademySoftwareFoundation/OpenACES/blob/main/aces/csc/Apple/CSC.Apple.AppleLog2_to_ACES.ctl) (ACES Input and Colorspaces)

### ACR Rendering Pipeline and Inverse Tone Curve

In ACR's rendering pipeline (confirmed via DNG SDK 1.7.1 `dng_render.cpp`), the
processing order is:

```
Camera Raw → Matrix+WB → HueSatMap → Exposure → LookTable
  → TONE CURVE (ACR3 S-curve) → RGBTables (Creative Profile 3D LUT) → Output
```

The Creative Profile's 3D LUT (RGBTable) receives data that has already been
tone-curved by ACR's default S-curve (the `dng_tone_curve_acr3_default` from
`dng_render.cpp`). Since the Fujifilm film simulation LUTs are designed for flat
log footage and include their own tone curve, applying them on top of ACR's S-curve
would produce double tone mapping.

**Solution**: Bake the inverse of ACR's default tone curve into the LUT input.
The 1025-entry inverse curve is extracted from the DNG SDK
(`dng_render.cpp` lines 444-703, `dng_tone_curve_acr3_default::EvaluateInverse`).

**Exposure offset compensation:** After undoing ACR3, the recovered scene-linear
values produce a result that is ~1 stop darker than ACR's default rendering. This
is because ACR3's S-curve boosts 18% gray by approximately 2.16x (+1.11 stops),
while Fujifilm's film simulation tone curves are more conservative (designed for
flat F-Log2C input). To match ACR's default brightness level, a configurable
exposure offset (default: +1.0 stop) is applied after the ACR3 inverse.

**Base profile dependency:** The inverse is specifically the inverse of the ACR3
default tone curve. If the selected camera profile (DCP) has a valid
`ProfileToneCurve` (DNG tag 50940), it **replaces** the ACR3 default in the
pipeline. This means the inverse cancellation is only exact when the user selects
"Adobe Standard" as the base profile. Other profiles ("Adobe Color", camera-matching
DCPs like "Camera PROVIA") embed their own tone curves. The Creative Profile XMP
format has no attribute to force a specific base profile.

### Creative Profile Binary Format

The Creative Profile format was reverse-engineered from the DNG SDK source code
(`dng_big_table.cpp`) and the open-source XMPconverter project:

**Binary blob structure** (little-endian):

| Offset | Type | Content |
|---|---|---|
| 0 | 4 × uint32 | Header: `[1, 1, 3, grid_size]` |
| 16 | N³×3 × uint16 | Delta-encoded LUT data (B-fastest, G-middle, R-slowest) |
| 16 + N³×6 | 3 × uint32 | Footer: `[colors, gamma, gamut]` |
| +12 | 2 × float64 | Amount slider range: `[min_range, max_range]` |

**Delta encoding**: Each uint16 LUT sample stores
`(absolute_value - identity_value) & 0xFFFF`, where
`identity = (index × 0xFFFF + (size >> 1)) // (size - 1)` (integer division).

**Compression**: zlib level 6, prepended with 4-byte LE uncompressed size.

**Base-85 encoding**: Custom 85-character XML-safe table (not standard Z85 or Ascii85).
Little-endian uint32 grouping, LSB-first digit ordering.

**XMP attributes**: The compressed+encoded blob is stored as `crs:Table_{MD5}`.
`crs:RGBTable` references the same MD5 hash (uppercase hex of the raw blob).

**Footer codes**: colors: 0=sRGB, 1=AdobeRGB, 2=ProPhoto, 3=P3, 4=Rec2020;
gamma: 1=sRGB, 2=ProPhoto(1.8), 3=AdobeRGB(2.2), 4=Rec2020;
gamut: 0=clip, 1=extend.

---

## Known Limitations

- **Double tone mapping** (ProPhoto `.cube` LUT variant only): The Fujifilm LUTs
  include their own tone curve. If the input image was developed with a RAW processor
  that applies its own tone curve (e.g., Adobe Camera Raw / Lightroom), the Fujifilm
  tone curve stacks on top, producing double tone mapping. This is not an issue if
  the RAW developer outputs a linear (flat) tone curve, or if you use the **ACR
  Creative Profiles** (which bake the inverse of ACR's default tone curve into the
  LUT input).
- **Gamma 2.2 assumption** (ProPhoto variant only): The original LUT output gamma is
  assumed to be pure power 2.2. The ACES display variants are unaffected since they
  pass through the original LUT output unchanged.
- **AP0 input domain [0, 1]**: For the linear AP0 variant, scene-linear values above
  1.0 are clamped. The ACEScct variant does not have this limitation (covers ~10 stops
  above 18% gray). Use ACEScct for content with bright highlights.

---

## Disclaimer

This project is not affiliated with, endorsed by, or sponsored by FUJIFILM Corporation.
Film simulation names (PROVIA, Velvia, ASTIA, CLASSIC CHROME, ETERNA, ACROS, REALA ACE,
etc.) are trademarks of FUJIFILM Corporation. These names are used here solely to
identify the film simulation looks that the LUTs are derived from.

The output LUTs are derived from Fujifilm's officially distributed F-Log2C 3D LUTs
through color space transformations. The source LUTs are not included in this
repository; see [Reproducing the LUTs](#reproducing-the-luts) for download
instructions.
