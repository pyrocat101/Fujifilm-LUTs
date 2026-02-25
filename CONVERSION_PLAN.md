# Fujifilm Film Simulation LUT Conversion Plan

## Objective

Create 3D LUTs and **ACR/Lightroom Creative Profiles** that apply Fujifilm's film
simulation looks to images in **ACES**, **ProPhoto RGB**, **Apple Log**, and
**Adobe Camera Raw / Lightroom** color spaces, derived from the official F-Log2C /
F-Gamut C LUTs.

---

## Source Material

- **10 film simulation 3D LUTs** (65-grid `.cube`, input: F-Log2C / F-Gamut C, output: BT.709 / Gamma 2.2)
  - ETERNA, PROVIA, Velvia, ASTIA, CLASSIC CHROME, REALA ACE,
    PRO Neg.Std, CLASSIC Neg., ETERNA BLEACH BYPASS, ACROS
- **F-Log2C spec** (`F-Log2C_DataSheet_E_Ver.1.0.pdf`) -- transfer function + F-Gamut C primaries
- **Fujifilm IDT** (`FUJIFILM_IDT_F-Log2C_Ver.1.00.ctl`) -- official F-GamutC-to-ACES-AP0 matrix (includes D65 -> D60 adaptation)
- **Apple Log Profile White Paper** (Apple Inc., 2023) -- Apple Log transfer function constants
- **Apple Log 2 CSC** (`CSC.Apple.AppleLog2_to_ACES.ctl`) -- Apple Gamut primaries
- **2 utility LUTs** (WDR, FLog2C-709) -- excluded from conversion

---

## Target LUT Variants

We produce **5 variant families** x 10 film sims x 2 grid sizes (65 and 33) =
**100 `.cube` LUT files**, plus **10 ACR Creative Profile** `.xmp` files.

### Variant 1 -- ProPhoto RGB (gamma 1.8) -> ProPhoto RGB (gamma 1.8)

| Property | Value |
|---|---|
| **Use case** | Photoshop: standard ProPhoto RGB document, 3D LUT adjustment layer |
| **Input** | ProPhoto RGB, gamma 1.8 (D50), domain [0, 1] |
| **Output** | ProPhoto RGB, gamma 1.8 (D50) -- film sim look baked in, colors within BT.709 gamut |
| **Pipeline** | ProPhoto(γ1.8) -> ProPhoto(lin) -> F-GamutC(lin) -> F-Log2C -> **[LUT]** -> BT.709(γ2.2) -> BT.709(lin) -> ProPhoto(lin) -> ProPhoto(γ1.8) |
| **Why gamma 1.8** | Matches Photoshop's built-in ProPhoto RGB profile. No custom ICC profile needed. Camera Raw outputs this natively. Better shadow precision than linear (18% gray at grid index ~25 vs ~11). |

### Variant 2 -- ACEScct (AP1, log) -> BT.709 / Gamma 2.2

| Property | Value |
|---|---|
| **Use case** | Display transform in DaVinci Resolve ACES pipeline (replaces ODT) |
| **Input** | ACEScct (AP1 primaries, log encoding, D60), domain [0, 1] |
| **Output** | BT.709 / Gamma 2.2 (display-referred) |
| **Pipeline** | ACEScct -> AP1(lin) -> F-GamutC(lin) -> F-Log2C -> **[LUT]** -> output |
| **Why ACEScct** | Matches Resolve's ACEScct node tree directly. Log encoding gives excellent shadow precision (18% gray at grid index ~26). Covers ~10 stops above 18% gray, vs only ~2.5 stops with linear ACEScg. |

### Variant 3 -- ACES2065-1 (AP0, linear) -> BT.709 / Gamma 2.2

| Property | Value |
|---|---|
| **Use case** | Universal/archival ACES display transform (Nuke, custom pipelines) |
| **Input** | Linear ACES2065-1 / AP0 (D60), domain [0, 1] |
| **Output** | BT.709 / Gamma 2.2 (display-referred) |
| **Pipeline** | AP0(lin) -> F-GamutC(lin) -> F-Log2C -> **[LUT]** -> output |
| **Note** | AP0 is strictly wider than F-Gamut C, so the input gamut conversion is lossless. |

### Variant 4 -- Apple Log (BT.2020) -> BT.709 / Gamma 2.2

| Property | Value |
|---|---|
| **Use case** | Display LUT for iPhone 15/16 Pro Apple Log footage |
| **Input** | Apple Log (BT.2020 primaries, D65), domain [0, 1] |
| **Output** | BT.709 / Gamma 2.2 (display-referred) |
| **Pipeline** | Apple Log -> BT.2020(lin) -> F-GamutC(lin) -> F-Log2C -> **[LUT]** -> output |

### Variant 5 -- Apple Log 2 (Apple Gamut) -> BT.709 / Gamma 2.2

| Property | Value |
|---|---|
| **Use case** | Display LUT for iPhone 17 Pro Apple Log 2 footage |
| **Input** | Apple Log 2 (Apple Gamut primaries, D65), domain [0, 1] |
| **Output** | BT.709 / Gamma 2.2 (display-referred) |
| **Pipeline** | Apple Log -> AppleGamut(lin) -> F-GamutC(lin) -> F-Log2C -> **[LUT]** -> output |
| **Note** | Same transfer function as Apple Log; only the color primaries differ. |

### Variant 6 -- ACR / Lightroom Creative Profiles (.xmp)

| Property | Value |
|---|---|
| **Use case** | Adobe Camera Raw / Lightroom: native profile browser with Amount slider |
| **Input** | ProPhoto RGB (gamma 1.8) -- as received by ACR's RGBTable pipeline stage |
| **Output** | ProPhoto RGB (gamma 1.8) -- film sim look baked in |
| **Grid size** | 32x32x32 (maximum supported by ACR Creative Profiles) |
| **Pipeline** | ProPhoto(γ1.8) -> ProPhoto(lin) -> **ACR3 inverse** -> **+1 stop exposure offset** -> F-GamutC(lin) -> F-Log2C -> **[LUT]** -> BT.709(γ2.2) -> BT.709(lin) -> ProPhoto(lin) -> ProPhoto(γ1.8) |

---

## Color Science Details

### Color Primaries (CIE xy chromaticity)

| Space | R | G | B | White |
|---|---|---|---|---|
| F-Gamut C | (0.7347, 0.2653) | (0.0263, 0.9737) | (0.1173, -0.0224) | D65 (0.3127, 0.3290) |
| BT.709 | (0.6400, 0.3300) | (0.3000, 0.6000) | (0.1500, 0.0600) | D65 (0.3127, 0.3290) |
| ProPhoto (ROMM) | (0.7347, 0.2653) | (0.1596, 0.8404) | (0.0366, 0.0001) | D50 (0.3457, 0.3585) |
| ACEScg (AP1) | (0.7130, 0.2930) | (0.1650, 0.8300) | (0.1280, 0.0440) | D60 (0.32168, 0.33767) |
| ACES2065-1 (AP0) | (0.7347, 0.2653) | (0.0000, 1.0000) | (0.0001, -0.0770) | D60 (0.32168, 0.33767) |
| BT.2020 | (0.7080, 0.2920) | (0.1700, 0.7970) | (0.1310, 0.0460) | D65 (0.3127, 0.3290) |
| Apple Gamut | (0.7250, 0.3010) | (0.2210, 0.8140) | (0.0680, -0.0760) | D65 (0.3127, 0.3290) |

### Transfer Functions

#### F-Log2C

Constants: `a=5.555556, b=0.064829, c=0.245281, d=0.384316, e=8.799461, f=0.092864`

```
Linear -> F-Log2C:
  if in >= 0.000889:  out = c * log10(a * in + b) + d
  else:               out = e * in + f
```

#### ACEScct (ACES S-2016-001)

```
Linear -> ACEScct:
  if in > 0.0078125:  out = (log2(in) + 9.72) / 17.52
  else:               out = 10.5402377416545 * in + 0.0729055341958355

ACEScct -> Linear:
  if in > 0.155251:   out = 2^(in * 17.52 - 9.72)
  else:               out = (in - 0.0729055341958355) / 10.5402377416545
```

#### Apple Log (Apple Log Profile White Paper, Apple Inc. 2023)

Constants: `R0=-0.05641088, Rt=0.01, C=47.28711236, B=0.00964052, G=0.08550479, D=0.69336945`

```
Linear -> Apple Log:
  if in < R0:   out = 0.0                      (floor)
  if in < Rt:   out = C * (in - R0)^2          (parabolic)
  else:         out = G * log2(in + B) + D      (log)

Apple Log -> Linear:
  if in < 0.0:            out = R0
  if in < C*(Rt-R0)^2:    out = sqrt(in / C) + R0
  else:                    out = 2^((in - D) / G) - B
```

Used by both Apple Log (BT.2020 primaries) and Apple Log 2 (Apple Gamut primaries).

#### ProPhoto RGB gamma

Standard ROMM RGB: `encoded = linear^(1/1.8)`, `linear = encoded^1.8`

### Chromatic Adaptation

Bradford transform for white point conversions:

- **D50 <-> D65**: ProPhoto <-> F-Gamut C and BT.709
- **D60 <-> D65**: ACES (AP0/AP1) <-> F-Gamut C and BT.709
- **No CAT needed**: BT.2020 and Apple Gamut share the D65 white point with F-Gamut C

### Conversion Matrices

The ACES conversion matrices are derived from **official reference sources** rather than
computed from primaries + Bradford adaptation (which produces a discrepancy due to the
non-standard D60 white point used in ACES):

- **AP0 -> F-Gamut C**: Inverse of the official Fujifilm IDT matrix
- **AP1 -> F-Gamut C**: Composed as `inv(IDT) @ ACES_AP1_to_AP0` (S-2014-004)
- **ProPhoto -> F-Gamut C**: Computed from primaries + Bradford adaptation (D50->D65)
- **BT.709 -> ProPhoto**: Computed from primaries + Bradford adaptation (D65->D50)
- **BT.2020 -> F-Gamut C**: Computed from primaries (both D65, no CAT)
- **Apple Gamut -> F-Gamut C**: Computed from primaries (both D65, no CAT)

```
# From FUJIFILM_IDT_F-Log2C_Ver.1.00.ctl (F-GamutC lin -> AP0 lin):
[[ 0.84075669532565,  0.04423586200772,  0.11500744266663],
 [-0.00051739528808,  1.01221071623543, -0.01169332094735],
 [-0.00817253004405, -0.00560807817457,  1.01378060821862]]

# Standard ACES AP1-to-AP0 (from S-2014-004):
[[ 0.6954522414,  0.1406786965,  0.1638690622],
 [ 0.0447945634,  0.8596711185,  0.0955343182],
 [-0.0055258826,  0.0040252103,  1.0015006723]]
```

---

## Implementation

### Script: `generate_luts.py`

```
Dependencies: Python 3 (>=3.10), NumPy
Run: uv run generate_luts.py
(dependencies declared as PEP 723 inline script metadata)
```

### Script: `generate_profiles.py`

```
Dependencies: Python 3 (>=3.10), NumPy
Run: uv run generate_profiles.py
(imports from generate_luts.py for shared color science functions)
```

### Output Directory Structure

```
output/
  ACR_profiles/
    Fujifilm PROVIA.xmp
    Fujifilm Velvia.xmp
    ...
  ProPhoto/
    ProPhoto_to_PROVIA_65grid.cube
    ProPhoto_to_PROVIA_33grid.cube
    ...
  ACEScct_display/
    ACEScct_to_PROVIA_65grid.cube
    ACEScct_to_PROVIA_33grid.cube
    ...
  AP0_display/
    AP0_to_PROVIA_65grid.cube
    AP0_to_PROVIA_33grid.cube
    ...
  AppleLog_display/
    AppleLog_to_PROVIA_65grid.cube
    AppleLog_to_PROVIA_33grid.cube
    ...
  AppleLog2_display/
    AppleLog2_to_PROVIA_65grid.cube
    AppleLog2_to_PROVIA_33grid.cube
    ...
```

---

## Verification Results

### LUT Generation (`generate_luts.py`)

1. **Matrix round-trip**: `IDT @ inv(IDT) = identity` (max diff 1.2e-17). PASS.

2. **White point preservation**: (1,1,1) in each input space maps to ~(1,1,1)
   in F-Gamut C. PASS for all 5 input spaces (ProPhoto, AP1, AP0, BT.2020,
   Apple Gamut).

3. **F-Log2C encoding**: Verified against documented reference points --
   0% -> code 95, 18% -> code 400, 90% -> code 570. PASS.

4. **ACEScct transfer function**: Round-trip max error 2.1e-14. Cut point
   continuity diff 1.7e-16. 18% gray -> ACEScct 0.4136 (grid index ~26.5).
   ACEScct=1.0 -> linear 222.9 (~10.3 stops above 18% gray). PASS.

5. **Apple Log transfer function**: Round-trip max error < 1e-10. Cut point
   continuity verified (quadratic and log segments meet at Rt=0.01).
   18% gray -> Apple Log 0.486 (grid index ~31.2). PASS.

6. **Neutral axis test**: Max differences ~0.001 (ProPhoto), ~0.002 (ACEScct),
   ~0.002 (AP0), at 18% gray. Expected interpolation error from 65-grid.

### Creative Profile Generation (`generate_profiles.py`)

1. **ACR3 inverse curve**: 1025 entries, monotonically increasing, endpoints [0, 1].
   Values match DNG SDK source exactly (verified entry-by-entry). 18% gray
   round-trips correctly: `acr3_inverse(0.39) ≈ 0.18` (within 0.002). PASS.

2. **Base-85 round-trip**: Tested for lengths [1, 2, 3, 4, 5, 16, 100, 1000]
   bytes. Exact bit-for-bit reconstruction. PASS.

3. **XMP structure** (PROVIA profile): Valid XML, MD5 integrity verified,
   header `[1, 1, 3, 32]`, footer `[ProPhoto, γ1.8, clip, 0-200%]`. PASS.

4. **LUT data reconstruction** (PROVIA profile): Black corner near zero
   (all channels < 1000/65535), white corner well above zero
   (all channels > 30000/65535). Mid-gray neutrality spread reported. PASS.

5. **All 10 profiles**: Exist and parse as valid XML. PASS.

---

## ACR Rendering Pipeline and Inverse Tone Curve

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

### Exposure Offset Compensation

After undoing ACR3, the recovered scene-linear values produce a result that is ~1
stop darker than ACR's default rendering. This is because ACR3's S-curve boosts
18% gray by approximately 2.16x (+1.11 stops), while Fujifilm's film simulation
tone curves are more conservative (designed for flat F-Log2C input).

To match ACR's default brightness level, a configurable exposure offset is applied
after the ACR3 inverse:

```
gamma 1.8 decode → inverse ACR3 S-curve → ×2^EXPOSURE_OFFSET_STOPS → scene-linear
```

`EXPOSURE_OFFSET_STOPS` defaults to `1.0`. At 18% gray, this reduces the brightness
mismatch from +1.11 stops to +0.09 stops. Set to `0.0` for the "pure" Fujifilm
rendering from scene-linear (will appear ~1 stop darker than ACR's default look).

### Base Profile Dependency

The inverse is specifically the inverse of the ACR3 default tone curve
(`dng_tone_curve_acr3_default`). In the DNG SDK's `Render()` method (lines
2145-2162), if the selected camera profile (DCP) has a valid `ProfileToneCurve`,
it **replaces** the ACR3 default. This means the inverse cancellation is only
exact when the user selects "Adobe Standard" as the base profile (which uses
the ACR3 default). Other profiles ("Adobe Color", camera-matching DCPs like
"Camera PROVIA") embed their own tone curves. The Creative Profile XMP format
has no attribute to force a specific base profile (`crs:PresetType="Look"` is
purely an overlay).

The `ProfileToneCurve` (DNG tag 50940) is a DCP-only feature and cannot be
included in XMP Creative Profiles. Similarly, `crs:ToneCurvePV2012` is a
user-level control that operates at a different point in the pipeline and
cannot override the profile-level tone curve.

---

## XMP / Binary Format (Reverse-Engineered)

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

1. **Double tone mapping** (ProPhoto `.cube` LUT variant only): The Fujifilm LUTs are
   designed for flat F-Log2C footage and include their own tone curve. When used as a
   look LUT in Photoshop, the input image has already been tone-mapped by Camera Raw,
   so the Fujifilm tone curve is applied on top. The ACR Creative Profiles solve this
   by baking the inverse of ACR's default tone curve into the LUT input.

2. **Gamma 2.2 assumption** (ProPhoto variant only): The original LUT output gamma
   is assumed to be pure power 2.2. The ACES and Apple Log display variants are
   unaffected since they pass through the original output unchanged.

3. **AP0 input domain [0, 1]**: For the linear AP0 variant, scene-linear values above
   1.0 are clamped (~2.5 stops above 18% gray). Use ACEScct for content with bright
   highlights (~10 stops coverage).

4. **Gamut boundary colors**: Extreme colors in ProPhoto or AP1 that fall slightly
   outside F-Gamut C will be clamped before F-Log2C encoding. This affects only
   imaginary or extreme-saturation colors that the film simulation would map to
   BT.709 boundary anyway.

5. **Apple Log vs Apple Log 2**: These use different color primaries (BT.2020 vs
   Apple Gamut). Using the wrong variant will produce incorrect colors. Check which
   format your device records: iPhone 15/16 Pro use Apple Log, iPhone 17 Pro uses
   Apple Log 2.
