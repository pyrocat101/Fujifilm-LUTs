# Fujifilm Film Simulation LUTs for ACES & ProPhoto RGB

3D LUTs that apply Fujifilm's official film simulation looks to images in
**ACES** (ACEScct / ACES2065-1) and **ProPhoto RGB** color spaces.

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
  ProPhoto/                 # ProPhoto RGB (gamma 1.8) -> ProPhoto RGB (gamma 1.8)
    ProPhoto_to_PROVIA_65grid.cube
    ProPhoto_to_ETERNA_65grid.cube
    ...

  ACEScct_display/          # ACEScct (AP1, log) -> BT.709 / Gamma 2.2
    ACEScct_to_PROVIA_65grid.cube
    ...

  AP0_display/              # Linear ACES2065-1 (AP0) -> BT.709 / Gamma 2.2
    AP0_to_PROVIA_65grid.cube
    ...
```

All LUTs are 65-grid `.cube` files with input domain [0, 1].

### What each variant does

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

Both ACES variants **replace** (not supplement) the ACES Output Transform.

---

## Recommended Workflows

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

### Other Applications

The `.cube` files work in any application that supports 3D LUTs (Premiere Pro,
Final Cut Pro, etc.). Ensure the input matches the expected color space and encoding:

- `ProPhoto/` LUTs: input must be **ProPhoto RGB, gamma 1.8**
- `ACEScct_display/` LUTs: input must be **ACEScct** (AP1 primaries, log encoding)
- `AP0_display/` LUTs: input must be **linear ACES2065-1 (AP0)**

---

## Reproducing the LUTs

### Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python package runner)
- The original Fujifilm F-Log2C 3D LUTs in
  `gfx-eterna-55-3d-lut-v100/65Grid/F-Log2C/`
  (download from the [Fujifilm support page](https://fujifilm-x.com/en-us/support/download/software/lut/))

### Generate

```sh
uv run generate_luts.py
```

This reads the 10 source film simulation LUTs, computes color space conversion
matrices, and writes 30 output LUTs to `output/`. Takes a few seconds.

The script runs built-in verification:
- Matrix round-trip and white point preservation
- F-Log2C encoding against Fujifilm's documented reference points
- ACEScct transfer function round-trip and cut point continuity
- Neutral axis comparison between original and generated LUTs

---

## Technical Details

### Conversion Pipeline

Each output LUT bakes the following chain into a single 65-grid 3D LUT:

```
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
```

### Color Space Matrices

- **AP0/AP1 to F-Gamut C**: Derived from the official Fujifilm IDT matrix
  (`FUJIFILM_IDT_F-Log2C_Ver.1.00.ctl`) and the standard ACES AP1-to-AP0 matrix
  (S-2014-004). Not computed from primaries + Bradford, since the ACES D60 white
  point produces a discrepancy with generic Bradford adaptation.
- **ProPhoto to F-Gamut C** and **BT.709 to ProPhoto**: Computed from primaries
  with Bradford chromatic adaptation (D50/D65).

### Source Data

- Film simulation LUTs: Fujifilm GFX ETERNA 55, V1.00
- F-Log2C transfer function: `F-Log2C_DataSheet_E_Ver.1.0.pdf`
- F-Gamut C to ACES matrix: `FUJIFILM_IDT_F-Log2C_Ver.1.00.ctl`
- ACEScct transfer function: ACES S-2016-001

---

## Known Limitations

- **Double tone mapping** (ProPhoto variant only): The Fujifilm LUTs are designed for
  flat F-Log2C footage and include their own tone curve. When used as a look LUT in
  Photoshop, the input image has already been tone-mapped by Camera Raw (baseline
  curve, highlights/shadows, etc.), so the Fujifilm tone curve is applied on top of
  ACR's. The result will have different contrast than Camera Raw's camera-matching
  DCP profiles (e.g., "Camera PROVIA/Standard"), which integrate the film simulation
  look into ACR's own rendering. The ACES display variants do not have this issue
  since they are used as the sole display transform.
- **Gamma 2.2 assumption** (ProPhoto variant only): The original LUT output gamma is
  assumed to be pure power 2.2. The ACES display variants are unaffected since they
  pass through the original LUT output unchanged.
- **AP0 input domain [0, 1]**: For the linear AP0 variant, scene-linear values above
  1.0 are clamped. The ACEScct variant does not have this limitation (covers ~10 stops
  above 18% gray). Use ACEScct for content with bright highlights.
