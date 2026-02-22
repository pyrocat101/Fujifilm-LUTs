#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy"]
# ///
"""
Generate Fujifilm Film Simulation LUTs for ACES and ProPhoto RGB color spaces.

Reads the original F-Log2C / F-Gamut C .cube LUTs and produces new LUTs with
different input color spaces:
  - Variant 1: ProPhoto RGB (gamma 1.8) -> ProPhoto RGB (gamma 1.8) (photo look LUT)
  - Variant 2: ACEScct (AP1, log) -> BT.709 / Gamma 2.2 (display LUT for Resolve)
  - Variant 3: Linear ACES2065-1 (AP0) -> BT.709 / Gamma 2.2 (display LUT)
"""

import os
import numpy as np

# =============================================================================
# Color Science Constants
# =============================================================================

# CIE xy chromaticity coordinates: (Rx, Ry, Gx, Gy, Bx, By)
PRIMARIES = {
    "F-Gamut C": (0.7347, 0.2653, 0.0263, 0.9737, 0.1173, -0.0224),
    "BT.709":    (0.6400, 0.3300, 0.3000, 0.6000, 0.1500,  0.0600),
    "ProPhoto":  (0.7347, 0.2653, 0.1596, 0.8404, 0.0366,  0.0001),
    "AP1":       (0.7130, 0.2930, 0.1650, 0.8300, 0.1280,  0.0440),
    "AP0":       (0.7347, 0.2653, 0.0000, 1.0000, 0.0001, -0.0770),
}

# CIE xy white points
WHITES = {
    "D65": (0.3127, 0.3290),
    "D50": (0.3457, 0.3585),
    "D60": (0.32168, 0.33767),
}

# Which white point each color space uses
SPACE_WHITE = {
    "F-Gamut C": "D65",
    "BT.709":    "D65",
    "ProPhoto":  "D50",
    "AP1":       "D60",
    "AP0":       "D60",
}

# Bradford chromatic adaptation matrix
BRADFORD_M = np.array([
    [ 0.8951,  0.2664, -0.1614],
    [-0.7502,  1.7135,  0.0367],
    [ 0.0389, -0.0685,  1.0296],
])
BRADFORD_M_INV = np.linalg.inv(BRADFORD_M)

# F-Log2C constants
FLOG2C_A = 5.555556
FLOG2C_B = 0.064829
FLOG2C_C = 0.245281
FLOG2C_D = 0.384316
FLOG2C_E = 8.799461
FLOG2C_F = 0.092864
FLOG2C_CUT1 = 0.000889  # linear threshold

# ACEScct constants (from ACES S-2016-001)
ACESCCT_CUT_LINEAR = 0.0078125       # 2^(-7), linear threshold
ACESCCT_CUT_CCT    = 0.155251141552511  # ACEScct value at the cut point
ACESCCT_SLOPE      = 10.5402377416545
ACESCCT_OFFSET     = 0.0729055341958355

# Fujifilm official F-GamutC -> AP0 matrix (from IDT, includes D65->D60 adaptation)
FUJIFILM_IDT_FGAMUTC_TO_AP0 = np.array([
    [ 0.84075669532565,  0.04423586200772,  0.11500744266663],
    [-0.00051739528808,  1.01221071623543, -0.01169332094735],
    [-0.00817253004405, -0.00560807817457,  1.01378060821862],
])

# Inverse: AP0 -> F-GamutC (derived from official IDT)
FUJIFILM_AP0_TO_FGAMUTC = np.linalg.inv(FUJIFILM_IDT_FGAMUTC_TO_AP0)

# Standard ACES AP1-to-AP0 matrix (from ACES S-2014-004, same white point so no CAT)
ACES_AP1_TO_AP0 = np.array([
    [ 0.6954522414,  0.1406786965,  0.1638690622],
    [ 0.0447945634,  0.8596711185,  0.0955343182],
    [-0.0055258826,  0.0040252103,  1.0015006723],
])

# Combined: AP1 -> F-GamutC = AP0_TO_FGAMUTC @ AP1_TO_AP0
ACES_AP1_TO_FGAMUTC = FUJIFILM_AP0_TO_FGAMUTC @ ACES_AP1_TO_AP0

# Film simulations to convert (filenames without path)
FILM_SIMS = [
    ("FLog2C_to_ETERNA_65grid_V.1.00.cube",       "ETERNA"),
    ("FLog2C_to_PROVIA_65grid_V.1.00.cube",        "PROVIA"),
    ("FLog2C_to_Velvia_65grid_V.1.00.cube",        "Velvia"),
    ("FLog2C_to_ASTIA_65grid_V.1.00.cube",         "ASTIA"),
    ("FLog2C_to_CLASSIC-CHROME_65grid_V.1.00.cube", "CLASSIC-CHROME"),
    ("FLog2C_to_REALA-ACE_65grid_V.1.00.cube",     "REALA-ACE"),
    ("FLog2C_to_PRO-Neg.Std_65grid_V.1.00.cube",   "PRO-Neg.Std"),
    ("FLog2C_to_CLASSIC-Neg._65grid_V.1.00.cube",  "CLASSIC-Neg."),
    ("FLog2C_to_ETERNA-BB_65grid_V.1.00.cube",     "ETERNA-BB"),
    ("FLog2C_to_ACROS_65grid_V.1.00.cube",         "ACROS"),
]

SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "gfx-eterna-55-3d-lut-v100", "65Grid", "F-Log2C"
)
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


# =============================================================================
# Color Science Utilities
# =============================================================================

def xy_to_XYZ(x, y):
    """Convert CIE xy chromaticity to XYZ (Y=1)."""
    return np.array([x / y, 1.0, (1.0 - x - y) / y])


def rgb_to_xyz_matrix(primaries, white_xy):
    """
    Compute the 3x3 RGB-to-XYZ matrix from CIE xy primaries and white point.

    primaries: (Rx, Ry, Gx, Gy, Bx, By)
    white_xy: (Wx, Wy)
    """
    Rx, Ry, Gx, Gy, Bx, By = primaries
    Wx, Wy = white_xy

    XYZ_R = xy_to_XYZ(Rx, Ry)
    XYZ_G = xy_to_XYZ(Gx, Gy)
    XYZ_B = xy_to_XYZ(Bx, By)

    M = np.column_stack([XYZ_R, XYZ_G, XYZ_B])
    W = xy_to_XYZ(Wx, Wy)
    S = np.linalg.solve(M, W)

    return M * S[np.newaxis, :]


def bradford_cat(src_white_xy, dst_white_xy):
    """Compute Bradford chromatic adaptation transform matrix."""
    src_XYZ = xy_to_XYZ(*src_white_xy)
    dst_XYZ = xy_to_XYZ(*dst_white_xy)

    src_lms = BRADFORD_M @ src_XYZ
    dst_lms = BRADFORD_M @ dst_XYZ

    scale = np.diag(dst_lms / src_lms)
    return BRADFORD_M_INV @ scale @ BRADFORD_M


def conversion_matrix(src_space, dst_space):
    """
    Compute combined 3x3 matrix to convert linear RGB from src_space to dst_space.
    Includes chromatic adaptation if white points differ.
    """
    src_prims = PRIMARIES[src_space]
    dst_prims = PRIMARIES[dst_space]
    src_white = WHITES[SPACE_WHITE[src_space]]
    dst_white = WHITES[SPACE_WHITE[dst_space]]

    M_src_to_xyz = rgb_to_xyz_matrix(src_prims, src_white)

    if src_white != dst_white:
        M_adapt = bradford_cat(src_white, dst_white)
        M_src_to_xyz = M_adapt @ M_src_to_xyz

    M_dst_to_xyz = rgb_to_xyz_matrix(dst_prims, dst_white)
    M_xyz_to_dst = np.linalg.inv(M_dst_to_xyz)

    return M_xyz_to_dst @ M_src_to_xyz


# =============================================================================
# Transfer Functions
# =============================================================================

def linear_to_flog2c(x):
    """Convert scene-linear reflection to F-Log2C (vectorized)."""
    x = np.asarray(x, dtype=np.float64)
    out = np.empty_like(x)
    mask = x >= FLOG2C_CUT1
    out[mask] = FLOG2C_C * np.log10(FLOG2C_A * x[mask] + FLOG2C_B) + FLOG2C_D
    out[~mask] = FLOG2C_E * x[~mask] + FLOG2C_F
    return out


def acescct_to_linear(x):
    """Convert ACEScct to scene-linear (vectorized). ACES S-2016-001."""
    x = np.asarray(x, dtype=np.float64)
    out = np.empty_like(x)
    mask = x > ACESCCT_CUT_CCT
    out[mask] = np.power(2.0, x[mask] * 17.52 - 9.72)
    out[~mask] = (x[~mask] - ACESCCT_OFFSET) / ACESCCT_SLOPE
    return out


def linear_to_acescct(x):
    """Convert scene-linear to ACEScct (vectorized). For verification."""
    x = np.asarray(x, dtype=np.float64)
    out = np.empty_like(x)
    mask = x > ACESCCT_CUT_LINEAR
    out[mask] = (np.log2(x[mask]) + 9.72) / 17.52
    out[~mask] = ACESCCT_SLOPE * x[~mask] + ACESCCT_OFFSET
    return out


def gamma_decode(x, gamma):
    """Remove gamma encoding: encoded -> linear. x^gamma."""
    return np.power(np.clip(x, 0.0, 1.0), gamma)


def gamma_encode(x, gamma):
    """Apply gamma encoding: linear -> encoded. x^(1/gamma)."""
    return np.power(np.clip(x, 0.0, 1.0), 1.0 / gamma)


# =============================================================================
# .cube LUT I/O
# =============================================================================

def read_cube(filepath):
    """
    Read a .cube 3D LUT file.
    Returns (size, data) where data is a (size^3, 3) float64 array.
    """
    size = None
    data_lines = []

    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('LUT_3D_SIZE'):
                size = int(line.split()[-1])
                continue
            if line.startswith(('TITLE', 'DOMAIN_MIN', 'DOMAIN_MAX',
                                'LUT_1D_SIZE', 'LUT_1D_INPUT_RANGE',
                                'LUT_3D_INPUT_RANGE')):
                continue
            parts = line.split()
            if len(parts) >= 3:
                try:
                    data_lines.append([float(parts[0]), float(parts[1]), float(parts[2])])
                except ValueError:
                    continue

    if size is None:
        raise ValueError(f"No LUT_3D_SIZE found in {filepath}")

    data = np.array(data_lines, dtype=np.float64)
    expected = size ** 3
    if len(data) != expected:
        raise ValueError(f"Expected {expected} entries for size {size}, got {len(data)}")

    return size, data


def write_cube(filepath, size, data, title="", comments=None,
               domain_min=None, domain_max=None):
    """
    Write a .cube 3D LUT file.
    data: (size^3, 3) array.
    """
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    with open(filepath, 'w') as f:
        if title:
            f.write(f'TITLE "{title}"\n')
        if comments:
            for c in comments:
                f.write(f"# {c}\n")
        if domain_min is not None:
            f.write(f"DOMAIN_MIN {domain_min[0]:.6f} {domain_min[1]:.6f} {domain_min[2]:.6f}\n")
        if domain_max is not None:
            f.write(f"DOMAIN_MAX {domain_max[0]:.6f} {domain_max[1]:.6f} {domain_max[2]:.6f}\n")
        f.write(f"LUT_3D_SIZE {size}\n")
        f.write("\n")

        for i in range(len(data)):
            r, g, b = data[i]
            f.write(f"{r:.6f} {g:.6f} {b:.6f}\n")


# =============================================================================
# Trilinear Interpolation
# =============================================================================

def lut_lookup(lut_data, size, rgb):
    """
    Trilinear interpolation on a 3D LUT.

    lut_data: (size^3, 3) array, ordered R-fastest (R varies first, then G, then B).
    rgb: (N, 3) array of input values in [0, 1].
    Returns: (N, 3) array of interpolated output values.
    """
    rgb = np.clip(rgb, 0.0, 1.0)

    max_idx = size - 1
    coords = rgb * max_idx

    idx_low = np.floor(coords).astype(np.int32)
    idx_low = np.clip(idx_low, 0, max_idx - 1)
    idx_high = idx_low + 1
    idx_high = np.clip(idx_high, 0, max_idx)
    frac = coords - idx_low

    fr, fg, fb = frac[:, 0], frac[:, 1], frac[:, 2]

    def flat_idx(ri, gi, bi):
        return bi * (size * size) + gi * size + ri

    i000 = flat_idx(idx_low[:, 0],  idx_low[:, 1],  idx_low[:, 2])
    i100 = flat_idx(idx_high[:, 0], idx_low[:, 1],  idx_low[:, 2])
    i010 = flat_idx(idx_low[:, 0],  idx_high[:, 1], idx_low[:, 2])
    i110 = flat_idx(idx_high[:, 0], idx_high[:, 1], idx_low[:, 2])
    i001 = flat_idx(idx_low[:, 0],  idx_low[:, 1],  idx_high[:, 2])
    i101 = flat_idx(idx_high[:, 0], idx_low[:, 1],  idx_high[:, 2])
    i011 = flat_idx(idx_low[:, 0],  idx_high[:, 1], idx_high[:, 2])
    i111 = flat_idx(idx_high[:, 0], idx_high[:, 1], idx_high[:, 2])

    c000 = lut_data[i000]; c100 = lut_data[i100]
    c010 = lut_data[i010]; c110 = lut_data[i110]
    c001 = lut_data[i001]; c101 = lut_data[i101]
    c011 = lut_data[i011]; c111 = lut_data[i111]

    fr = fr[:, np.newaxis]
    fg = fg[:, np.newaxis]
    fb = fb[:, np.newaxis]

    c00 = c000 * (1 - fr) + c100 * fr
    c01 = c001 * (1 - fr) + c101 * fr
    c10 = c010 * (1 - fr) + c110 * fr
    c11 = c011 * (1 - fr) + c111 * fr

    c0 = c00 * (1 - fg) + c10 * fg
    c1 = c01 * (1 - fg) + c11 * fg

    return c0 * (1 - fb) + c1 * fb


# =============================================================================
# Pipeline Composition
# =============================================================================

def generate_grid(size, domain_min=0.0, domain_max=1.0):
    """
    Generate a (size^3, 3) grid of input RGB values.
    .cube ordering: R varies fastest, then G, then B.
    """
    steps = np.linspace(domain_min, domain_max, size)
    r, g, b = np.meshgrid(steps, steps, steps, indexing='ij')
    grid = np.stack([
        r.transpose(2, 1, 0).ravel(),
        g.transpose(2, 1, 0).ravel(),
        b.transpose(2, 1, 0).ravel(),
    ], axis=-1)
    return grid


def apply_matrix(rgb, matrix):
    """Apply a 3x3 color matrix to (N, 3) array of RGB values."""
    return rgb @ matrix.T


def process_variant(source_lut_data, source_lut_size, variant, grid_size=65):
    """
    Generate a new LUT for the specified variant.

    variant dict keys:
        matrix_in:      3x3 matrix, linear input space -> linear F-Gamut C
        input_decode:   callable(x) -> x, decodes input encoding to linear (or None)
        matrix_out:     3x3 matrix, linear BT.709 -> linear output space (or None)
        output_encode:  callable(x) -> x, encodes linear output (or None)
        output_gamma:   gamma to linearize from original LUT output (default 2.2)
    """
    M_in = variant["matrix_in"]
    input_decode = variant.get("input_decode")
    M_out = variant.get("matrix_out")
    output_encode = variant.get("output_encode")
    output_gamma = variant.get("output_gamma", 2.2)

    # Generate input grid [0, 1]
    grid = generate_grid(grid_size)

    # Step 1: Decode input encoding to linear (if needed)
    if input_decode is not None:
        linear_input = input_decode(grid)
    else:
        linear_input = grid

    # Step 2: Convert linear input space -> linear F-Gamut C
    fgamutc_linear = apply_matrix(linear_input, M_in)

    # Step 3: Clamp negative values (out-of-gamut for F-Gamut C)
    fgamutc_linear = np.maximum(fgamutc_linear, 0.0)

    # Step 4: Apply F-Log2C encoding
    flog2c = linear_to_flog2c(fgamutc_linear)

    # Step 5: Clamp to [0, 1] for LUT lookup
    flog2c = np.clip(flog2c, 0.0, 1.0)

    # Step 6: Look up in original LUT
    result = lut_lookup(source_lut_data, source_lut_size, flog2c)

    # Step 7 (look LUT only): Linearize output, convert gamut, re-encode
    if M_out is not None:
        result = gamma_decode(result, output_gamma)
        result = apply_matrix(result, M_out)
        result = np.clip(result, 0.0, 1.0)
        if output_encode is not None:
            result = output_encode(result)
            result = np.clip(result, 0.0, 1.0)

    return result


# =============================================================================
# Verification
# =============================================================================

def verify_matrices():
    """Verify matrices used in the pipeline."""
    print("=" * 60)
    print("MATRIX VERIFICATION")
    print("=" * 60)

    roundtrip = FUJIFILM_IDT_FGAMUTC_TO_AP0 @ FUJIFILM_AP0_TO_FGAMUTC
    identity_diff = np.max(np.abs(roundtrip - np.eye(3)))
    print(f"\n1. AP0 IDT round-trip (should be identity), max diff: {identity_diff:.2e}")
    print(f"   {'PASS' if identity_diff < 1e-12 else 'FAIL'}")

    white_ap1 = np.array([1.0, 1.0, 1.0])
    white_fgamutc = ACES_AP1_TO_FGAMUTC @ white_ap1
    white_diff = np.max(np.abs(white_fgamutc - 1.0))
    print(f"\n2. AP1 white (1,1,1) -> F-GamutC: {white_fgamutc}")
    print(f"   Max diff from (1,1,1): {white_diff:.6f}")
    print(f"   {'PASS' if white_diff < 0.05 else 'WARN'}")

    white_ap0 = np.array([1.0, 1.0, 1.0])
    white_fgamutc_ap0 = FUJIFILM_AP0_TO_FGAMUTC @ white_ap0
    white_diff_ap0 = np.max(np.abs(white_fgamutc_ap0 - 1.0))
    print(f"\n3. AP0 white (1,1,1) -> F-GamutC: {white_fgamutc_ap0}")
    print(f"   Max diff from (1,1,1): {white_diff_ap0:.6f}")
    print(f"   {'PASS' if white_diff_ap0 < 0.05 else 'WARN'}")

    M_prophoto = conversion_matrix("ProPhoto", "F-Gamut C")
    white_prophoto = M_prophoto @ np.array([1.0, 1.0, 1.0])
    white_diff_pp = np.max(np.abs(white_prophoto - 1.0))
    print(f"\n4. ProPhoto white (1,1,1) -> F-GamutC: {white_prophoto}")
    print(f"   Max diff from (1,1,1): {white_diff_pp:.6f}")
    print(f"   {'PASS' if white_diff_pp < 0.05 else 'WARN'}")

    print()


def verify_flog2c():
    """Verify F-Log2C encoding against known reference points."""
    print("=" * 60)
    print("F-LOG2C ENCODING VERIFICATION")
    print("=" * 60)

    test_points = [
        (0.0,  0.092864, 95),
        (0.18, 0.390625, 400),
        (0.90, 0.556641, 570),
    ]

    for linear, expected_float, expected_10bit in test_points:
        result = linear_to_flog2c(np.array([linear]))[0]
        result_10bit = round(result * 1023)
        diff = abs(result - expected_float)
        print(f"  Linear {linear:.2f} -> F-Log2C {result:.6f} "
              f"(expected ~{expected_float:.6f}, diff={diff:.6f}, "
              f"10-bit={result_10bit} expected={expected_10bit})")

    print()


def verify_acescct():
    """Verify ACEScct transfer function round-trip and known values."""
    print("=" * 60)
    print("ACESCCT TRANSFER FUNCTION VERIFICATION")
    print("=" * 60)

    # Known reference points (from ACES S-2016-001)
    test_points = [
        (0.0,     ACESCCT_OFFSET),          # 0 linear -> offset
        (0.18,    None),                     # 18% gray
        (1.0,     None),                     # 1.0 linear
    ]

    # 18% gray in ACEScct: (log2(0.18) + 9.72) / 17.52
    acescct_18 = (np.log2(0.18) + 9.72) / 17.52
    print(f"  18% gray -> ACEScct: {acescct_18:.6f} (grid index ~{acescct_18 * 64:.1f} of 64)")

    # 1.0 linear in ACEScct
    acescct_1 = (np.log2(1.0) + 9.72) / 17.52
    print(f"  1.0 linear -> ACEScct: {acescct_1:.6f} (grid index ~{acescct_1 * 64:.1f} of 64)")

    # Continuity at cut point
    linear_at_cut = ACESCCT_CUT_LINEAR
    cct_log = (np.log2(linear_at_cut) + 9.72) / 17.52
    cct_lin = ACESCCT_SLOPE * linear_at_cut + ACESCCT_OFFSET
    print(f"  Cut point continuity: log={cct_log:.12f}, linear={cct_lin:.12f}, "
          f"diff={abs(cct_log - cct_lin):.2e}")

    # Round-trip test
    test_vals = np.array([0.0, 0.001, 0.01, 0.18, 0.5, 1.0, 5.0, 16.0, 50.0])
    encoded = linear_to_acescct(test_vals)
    decoded = acescct_to_linear(encoded)
    max_roundtrip_err = np.max(np.abs(decoded - test_vals))
    print(f"  Round-trip max error: {max_roundtrip_err:.2e}")
    print(f"  {'PASS' if max_roundtrip_err < 1e-10 else 'FAIL'}")

    # Dynamic range: what linear value does ACEScct=1.0 correspond to?
    linear_at_1 = acescct_to_linear(np.array([1.0]))[0]
    stops_above_18 = np.log2(linear_at_1 / 0.18)
    print(f"  ACEScct=1.0 -> linear={linear_at_1:.1f} "
          f"(~{stops_above_18:.1f} stops above 18% gray)")

    print()


def verify_neutral_axis(source_lut_data, source_lut_size, new_lut_data, new_lut_size,
                        variant):
    """
    Verify that neutral grays through the new LUT produce results consistent
    with the corresponding F-Log2C values through the original LUT.
    """
    name = variant["name"]
    M_in = variant["matrix_in"]
    input_decode = variant.get("input_decode")
    M_out = variant.get("matrix_out")
    output_encode = variant.get("output_encode")
    output_gamma = variant.get("output_gamma", 2.2)

    print(f"  Neutral axis test for {name}:")

    # Test linear gray levels
    for linear_gray in [0.05, 0.10, 0.18, 0.50, 0.90]:
        # Compute what the input LUT value would be for this linear gray
        if input_decode is not None:
            # We need to find the encoded value that decodes to this linear gray.
            # For gamma: encoded = linear^(1/gamma)
            # For ACEScct: use linear_to_acescct
            if name == "ACEScct_display":
                input_val = linear_to_acescct(np.array([linear_gray]))[0]
            else:
                # ProPhoto gamma 1.8
                input_val = linear_gray ** (1.0 / 1.8)
        else:
            input_val = linear_gray

        # Path A: manual pipeline (linear gray -> F-Gamut C -> F-Log2C -> orig LUT)
        input_rgb = np.array([[linear_gray, linear_gray, linear_gray]])
        fgamutc = apply_matrix(input_rgb, M_in)
        fgamutc = np.maximum(fgamutc, 0.0)
        flog2c = linear_to_flog2c(fgamutc)
        flog2c = np.clip(flog2c, 0.0, 1.0)
        orig_result = lut_lookup(source_lut_data, source_lut_size, flog2c)[0]

        # If look LUT, also apply output conversion to orig_result for comparison
        if M_out is not None:
            orig_display = orig_result.copy()
            orig_linear = gamma_decode(orig_result.reshape(1, 3), output_gamma)
            orig_converted = apply_matrix(orig_linear, M_out)
            orig_converted = np.clip(orig_converted, 0.0, 1.0)
            if output_encode is not None:
                orig_converted = output_encode(orig_converted)
                orig_converted = np.clip(orig_converted, 0.0, 1.0)
            orig_result = orig_converted[0]

        # Path B: look up encoded value in new LUT
        new_input = np.array([[input_val, input_val, input_val]])
        new_result = lut_lookup(new_lut_data, new_lut_size, new_input)[0]

        diff = np.abs(orig_result - new_result).max()
        print(f"    Linear {linear_gray:.2f} (input={input_val:.4f}): "
              f"expected={orig_result}, got={new_result}, max_diff={diff:.6f}")

    print()


# =============================================================================
# Main
# =============================================================================

def main():
    print("Fujifilm Film Simulation LUT Generator")
    print("=" * 60)

    # Compute conversion matrices
    print("\nComputing conversion matrices...")

    M_prophoto_to_fgamutc = conversion_matrix("ProPhoto", "F-Gamut C")
    M_bt709_to_prophoto = conversion_matrix("BT.709", "ProPhoto")
    M_ap0_to_fgamutc = FUJIFILM_AP0_TO_FGAMUTC
    M_ap1_to_fgamutc = ACES_AP1_TO_FGAMUTC

    print("  ProPhoto -> F-Gamut C (computed via Bradford D50->D65):")
    print(f"    {M_prophoto_to_fgamutc}")
    print("  AP1 -> F-Gamut C (from Fujifilm IDT + ACES AP1->AP0):")
    print(f"    {M_ap1_to_fgamutc}")
    print("  AP0 -> F-Gamut C (inverted Fujifilm IDT):")
    print(f"    {M_ap0_to_fgamutc}")
    print("  BT.709 -> ProPhoto (computed via Bradford D65->D50):")
    print(f"    {M_bt709_to_prophoto}")

    # Run verification
    verify_matrices()
    verify_flog2c()
    verify_acescct()

    # Define variants
    variants = [
        {
            "name": "ProPhoto",
            "dir": "ProPhoto",
            "prefix": "ProPhoto_to_",
            "matrix_in": M_prophoto_to_fgamutc,
            "input_decode": lambda x: gamma_decode(x, 1.8),
            "matrix_out": M_bt709_to_prophoto,
            "output_gamma": 2.2,
            "output_encode": lambda x: gamma_encode(x, 1.8),
            "comments": [
                "Input: ProPhoto RGB, gamma 1.8 (D50)",
                "Output: ProPhoto RGB, gamma 1.8 (D50) with film simulation look",
                "Use: Photoshop 3D LUT adjustment layer on standard ProPhoto document",
            ],
        },
        {
            "name": "ACEScct_display",
            "dir": "ACEScct_display",
            "prefix": "ACEScct_to_",
            "matrix_in": M_ap1_to_fgamutc,
            "input_decode": acescct_to_linear,
            "matrix_out": None,
            "comments": [
                "Input: ACEScct (AP1 primaries, log encoding, D60)",
                "Output: BT.709 / Gamma 2.2 (display-referred)",
                "Use: Display/output transform in DaVinci Resolve ACES pipeline (replaces ODT)",
            ],
        },
        {
            "name": "AP0_display",
            "dir": "AP0_display",
            "prefix": "AP0_to_",
            "matrix_in": M_ap0_to_fgamutc,
            "input_decode": None,
            "matrix_out": None,
            "comments": [
                "Input: Linear ACES2065-1 / AP0 (D60)",
                "Output: BT.709 / Gamma 2.2 (display-referred)",
                "Use: Display/output transform in ACES pipeline (replaces ODT)",
            ],
        },
    ]

    # Process each film simulation x variant
    total = len(FILM_SIMS) * len(variants)
    count = 0

    for src_filename, sim_name in FILM_SIMS:
        src_path = os.path.join(SOURCE_DIR, src_filename)
        print(f"\nReading source LUT: {src_filename}")
        src_size, src_data = read_cube(src_path)
        print(f"  Size: {src_size}, entries: {len(src_data)}")

        for variant in variants:
            count += 1
            out_name = f"{variant['prefix']}{sim_name}_65grid.cube"
            out_path = os.path.join(OUTPUT_DIR, variant["dir"], out_name)

            title = f"{variant['prefix']}{sim_name}"
            comments = variant["comments"] + [
                f"Source: {src_filename}",
                "Generated from Fujifilm GFX ETERNA 55 F-Log2C LUT",
            ]

            print(f"  [{count}/{total}] Generating {out_name}...")

            new_data = process_variant(src_data, src_size, variant)
            write_cube(out_path, 65, new_data, title=title, comments=comments)

        # Run neutral axis verification on ETERNA
        if sim_name == "ETERNA":
            print("\n  --- Verification (ETERNA) ---")
            for variant in variants:
                out_name = f"{variant['prefix']}ETERNA_65grid.cube"
                out_path = os.path.join(OUTPUT_DIR, variant["dir"], out_name)
                new_size, new_data = read_cube(out_path)
                verify_neutral_axis(src_data, src_size, new_data, new_size, variant)

    print("\n" + "=" * 60)
    print(f"Done! Generated {count} LUT files in: {OUTPUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
