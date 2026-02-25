#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy"]
# ///
"""
Generate Adobe Camera Raw / Lightroom Creative Profiles (.xmp) from
Fujifilm Film Simulation LUTs.

Reads the original F-Log2C / F-Gamut C .cube LUTs and produces .xmp
Creative Profile files that can be installed in Lightroom / Camera Raw.

The profiles embed a 32x32x32 ProPhoto RGB (gamma 1.8) 3D LUT using
Adobe's binary format (delta-encoded, zlib-compressed, base-85 encoded).

Usage:
    uv run generate_profiles.py
"""

import os
import struct
import zlib
import hashlib
import time
import numpy as np

from generate_luts import (
    read_cube,
    process_variant,
    conversion_matrix,
    gamma_decode,
    gamma_encode,
    FILM_SIMS,
    SOURCE_DIR,
)

# =============================================================================
# Constants
# =============================================================================

GRID_SIZE = 32  # Max supported by ACR Creative Profiles

# Exposure offset (in stops) to compensate for the brightness difference between
# ACR's default rendering (ACR3 S-curve) and Fujifilm's film simulation tone curves.
# ACR3 boosts 18% gray by ~1.1 stops compared to the Fujifilm sims' own rendering.
# Without this offset, the Creative Profile looks ~1 stop dark relative to ACR's
# default look because we undo ACR3 but Fujifilm's curve is more conservative.
# Set to 0.0 to disable and get the "pure" Fujifilm rendering from scene-linear.
EXPOSURE_OFFSET_STOPS = 1.0

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "output", "ACR_profiles"
)

# Adobe's XML-safe base-85 encode table
# (from DNG SDK dng_big_table.cpp / XMPconverter)
B85_TABLE = b"0123456789abcdefghijklmnopqrstuvwxyz" \
            b"ABCDEFGHIJKLMNOPQRSTUVWXYZ" \
            b".-:+=^!/*?`'|()[]{}@%$#"

# Footer: color primaries and gamma codes
COLORS_PROPHOTO = 2   # 0=sRGB, 1=AdobeRGB, 2=ProPhoto, 3=P3, 4=Rec2020
GAMMA_PROPHOTO  = 2   # 1=sRGB, 2=ProPhoto(1.8), 3=AdobeRGB(2.2), 4=Rec2020
GAMUT_CLIP      = 0   # 0=clip, 1=extend

# ACR3 default tone curve inverse — 1025-entry lookup table
# Extracted from Adobe DNG SDK 1.7.1: dng_render.cpp lines 444-703
# (dng_tone_curve_acr3_default::EvaluateInverse)
#
# This is the inverse of the S-curve that ACR applies in its rendering
# pipeline BEFORE the Creative Profile's 3D LUT. By baking this inverse
# into the LUT input, we undo ACR's tone mapping so that only the
# Fujifilm film simulation's own tone curve is applied.
#
# Input: tone-curved linear value [0, 1]  (output of ACR3 S-curve)
# Output: original scene-linear value [0, 1]  (before ACR3 S-curve)
ACR3_INVERSE_TABLE = np.array([
    0.00000, 0.00121, 0.00237, 0.00362, 0.00496, 0.00621, 0.00738, 0.00848,
    0.00951, 0.01048, 0.01139, 0.01227, 0.01312, 0.01393, 0.01471, 0.01547,
    0.01620, 0.01692, 0.01763, 0.01831, 0.01899, 0.01965, 0.02030, 0.02094,
    0.02157, 0.02218, 0.02280, 0.02340, 0.02399, 0.02458, 0.02517, 0.02574,
    0.02631, 0.02688, 0.02744, 0.02800, 0.02855, 0.02910, 0.02965, 0.03019,
    0.03072, 0.03126, 0.03179, 0.03232, 0.03285, 0.03338, 0.03390, 0.03442,
    0.03493, 0.03545, 0.03596, 0.03647, 0.03698, 0.03749, 0.03799, 0.03849,
    0.03899, 0.03949, 0.03998, 0.04048, 0.04097, 0.04146, 0.04195, 0.04244,
    0.04292, 0.04341, 0.04389, 0.04437, 0.04485, 0.04533, 0.04580, 0.04628,
    0.04675, 0.04722, 0.04769, 0.04816, 0.04863, 0.04910, 0.04956, 0.05003,
    0.05049, 0.05095, 0.05141, 0.05187, 0.05233, 0.05278, 0.05324, 0.05370,
    0.05415, 0.05460, 0.05505, 0.05551, 0.05595, 0.05640, 0.05685, 0.05729,
    0.05774, 0.05818, 0.05863, 0.05907, 0.05951, 0.05995, 0.06039, 0.06083,
    0.06126, 0.06170, 0.06214, 0.06257, 0.06301, 0.06344, 0.06388, 0.06431,
    0.06474, 0.06517, 0.06560, 0.06602, 0.06645, 0.06688, 0.06731, 0.06773,
    0.06815, 0.06858, 0.06900, 0.06943, 0.06985, 0.07027, 0.07069, 0.07111,
    0.07152, 0.07194, 0.07236, 0.07278, 0.07319, 0.07361, 0.07402, 0.07444,
    0.07485, 0.07526, 0.07567, 0.07608, 0.07650, 0.07691, 0.07732, 0.07772,
    0.07813, 0.07854, 0.07895, 0.07935, 0.07976, 0.08016, 0.08057, 0.08098,
    0.08138, 0.08178, 0.08218, 0.08259, 0.08299, 0.08339, 0.08379, 0.08419,
    0.08459, 0.08499, 0.08539, 0.08578, 0.08618, 0.08657, 0.08697, 0.08737,
    0.08776, 0.08816, 0.08855, 0.08894, 0.08934, 0.08973, 0.09012, 0.09051,
    0.09091, 0.09130, 0.09169, 0.09208, 0.09247, 0.09286, 0.09324, 0.09363,
    0.09402, 0.09440, 0.09479, 0.09518, 0.09556, 0.09595, 0.09633, 0.09672,
    0.09710, 0.09749, 0.09787, 0.09825, 0.09863, 0.09901, 0.09939, 0.09978,
    0.10016, 0.10054, 0.10092, 0.10130, 0.10167, 0.10205, 0.10243, 0.10281,
    0.10319, 0.10356, 0.10394, 0.10432, 0.10469, 0.10507, 0.10544, 0.10582,
    0.10619, 0.10657, 0.10694, 0.10731, 0.10768, 0.10806, 0.10843, 0.10880,
    0.10917, 0.10954, 0.10991, 0.11029, 0.11066, 0.11103, 0.11141, 0.11178,
    0.11215, 0.11253, 0.11290, 0.11328, 0.11365, 0.11403, 0.11440, 0.11478,
    0.11516, 0.11553, 0.11591, 0.11629, 0.11666, 0.11704, 0.11742, 0.11780,
    0.11818, 0.11856, 0.11894, 0.11932, 0.11970, 0.12008, 0.12046, 0.12084,
    0.12122, 0.12161, 0.12199, 0.12237, 0.12276, 0.12314, 0.12352, 0.12391,
    0.12429, 0.12468, 0.12506, 0.12545, 0.12583, 0.12622, 0.12661, 0.12700,
    0.12738, 0.12777, 0.12816, 0.12855, 0.12894, 0.12933, 0.12972, 0.13011,
    0.13050, 0.13089, 0.13129, 0.13168, 0.13207, 0.13247, 0.13286, 0.13325,
    0.13365, 0.13404, 0.13444, 0.13483, 0.13523, 0.13563, 0.13603, 0.13642,
    0.13682, 0.13722, 0.13762, 0.13802, 0.13842, 0.13882, 0.13922, 0.13962,
    0.14003, 0.14043, 0.14083, 0.14124, 0.14164, 0.14204, 0.14245, 0.14285,
    0.14326, 0.14366, 0.14407, 0.14448, 0.14489, 0.14530, 0.14570, 0.14611,
    0.14652, 0.14693, 0.14734, 0.14776, 0.14817, 0.14858, 0.14900, 0.14941,
    0.14982, 0.15024, 0.15065, 0.15107, 0.15148, 0.15190, 0.15232, 0.15274,
    0.15316, 0.15357, 0.15399, 0.15441, 0.15483, 0.15526, 0.15568, 0.15610,
    0.15652, 0.15695, 0.15737, 0.15779, 0.15822, 0.15864, 0.15907, 0.15950,
    0.15992, 0.16035, 0.16078, 0.16121, 0.16164, 0.16207, 0.16250, 0.16293,
    0.16337, 0.16380, 0.16423, 0.16467, 0.16511, 0.16554, 0.16598, 0.16641,
    0.16685, 0.16729, 0.16773, 0.16816, 0.16860, 0.16904, 0.16949, 0.16993,
    0.17037, 0.17081, 0.17126, 0.17170, 0.17215, 0.17259, 0.17304, 0.17349,
    0.17393, 0.17438, 0.17483, 0.17528, 0.17573, 0.17619, 0.17664, 0.17709,
    0.17754, 0.17799, 0.17845, 0.17890, 0.17936, 0.17982, 0.18028, 0.18073,
    0.18119, 0.18165, 0.18211, 0.18257, 0.18303, 0.18350, 0.18396, 0.18442,
    0.18489, 0.18535, 0.18582, 0.18629, 0.18676, 0.18723, 0.18770, 0.18817,
    0.18864, 0.18911, 0.18958, 0.19005, 0.19053, 0.19100, 0.19147, 0.19195,
    0.19243, 0.19291, 0.19339, 0.19387, 0.19435, 0.19483, 0.19531, 0.19579,
    0.19627, 0.19676, 0.19724, 0.19773, 0.19821, 0.19870, 0.19919, 0.19968,
    0.20017, 0.20066, 0.20115, 0.20164, 0.20214, 0.20263, 0.20313, 0.20362,
    0.20412, 0.20462, 0.20512, 0.20561, 0.20611, 0.20662, 0.20712, 0.20762,
    0.20812, 0.20863, 0.20913, 0.20964, 0.21015, 0.21066, 0.21117, 0.21168,
    0.21219, 0.21270, 0.21321, 0.21373, 0.21424, 0.21476, 0.21527, 0.21579,
    0.21631, 0.21683, 0.21735, 0.21787, 0.21839, 0.21892, 0.21944, 0.21997,
    0.22049, 0.22102, 0.22155, 0.22208, 0.22261, 0.22314, 0.22367, 0.22420,
    0.22474, 0.22527, 0.22581, 0.22634, 0.22688, 0.22742, 0.22796, 0.22850,
    0.22905, 0.22959, 0.23013, 0.23068, 0.23123, 0.23178, 0.23232, 0.23287,
    0.23343, 0.23398, 0.23453, 0.23508, 0.23564, 0.23620, 0.23675, 0.23731,
    0.23787, 0.23843, 0.23899, 0.23956, 0.24012, 0.24069, 0.24125, 0.24182,
    0.24239, 0.24296, 0.24353, 0.24410, 0.24468, 0.24525, 0.24582, 0.24640,
    0.24698, 0.24756, 0.24814, 0.24872, 0.24931, 0.24989, 0.25048, 0.25106,
    0.25165, 0.25224, 0.25283, 0.25342, 0.25401, 0.25460, 0.25520, 0.25579,
    0.25639, 0.25699, 0.25759, 0.25820, 0.25880, 0.25940, 0.26001, 0.26062,
    0.26122, 0.26183, 0.26244, 0.26306, 0.26367, 0.26429, 0.26490, 0.26552,
    0.26614, 0.26676, 0.26738, 0.26800, 0.26863, 0.26925, 0.26988, 0.27051,
    0.27114, 0.27177, 0.27240, 0.27303, 0.27367, 0.27431, 0.27495, 0.27558,
    0.27623, 0.27687, 0.27751, 0.27816, 0.27881, 0.27945, 0.28011, 0.28076,
    0.28141, 0.28207, 0.28272, 0.28338, 0.28404, 0.28470, 0.28536, 0.28602,
    0.28669, 0.28736, 0.28802, 0.28869, 0.28937, 0.29004, 0.29071, 0.29139,
    0.29207, 0.29274, 0.29342, 0.29410, 0.29479, 0.29548, 0.29616, 0.29685,
    0.29754, 0.29823, 0.29893, 0.29962, 0.30032, 0.30102, 0.30172, 0.30242,
    0.30312, 0.30383, 0.30453, 0.30524, 0.30595, 0.30667, 0.30738, 0.30809,
    0.30881, 0.30953, 0.31025, 0.31097, 0.31170, 0.31242, 0.31315, 0.31388,
    0.31461, 0.31534, 0.31608, 0.31682, 0.31755, 0.31829, 0.31904, 0.31978,
    0.32053, 0.32127, 0.32202, 0.32277, 0.32353, 0.32428, 0.32504, 0.32580,
    0.32656, 0.32732, 0.32808, 0.32885, 0.32962, 0.33039, 0.33116, 0.33193,
    0.33271, 0.33349, 0.33427, 0.33505, 0.33583, 0.33662, 0.33741, 0.33820,
    0.33899, 0.33978, 0.34058, 0.34138, 0.34218, 0.34298, 0.34378, 0.34459,
    0.34540, 0.34621, 0.34702, 0.34783, 0.34865, 0.34947, 0.35029, 0.35111,
    0.35194, 0.35277, 0.35360, 0.35443, 0.35526, 0.35610, 0.35694, 0.35778,
    0.35862, 0.35946, 0.36032, 0.36117, 0.36202, 0.36287, 0.36372, 0.36458,
    0.36545, 0.36631, 0.36718, 0.36805, 0.36891, 0.36979, 0.37066, 0.37154,
    0.37242, 0.37331, 0.37419, 0.37507, 0.37596, 0.37686, 0.37775, 0.37865,
    0.37955, 0.38045, 0.38136, 0.38227, 0.38317, 0.38409, 0.38500, 0.38592,
    0.38684, 0.38776, 0.38869, 0.38961, 0.39055, 0.39148, 0.39242, 0.39335,
    0.39430, 0.39524, 0.39619, 0.39714, 0.39809, 0.39904, 0.40000, 0.40097,
    0.40193, 0.40289, 0.40386, 0.40483, 0.40581, 0.40679, 0.40777, 0.40875,
    0.40974, 0.41073, 0.41172, 0.41272, 0.41372, 0.41472, 0.41572, 0.41673,
    0.41774, 0.41875, 0.41977, 0.42079, 0.42181, 0.42284, 0.42386, 0.42490,
    0.42594, 0.42697, 0.42801, 0.42906, 0.43011, 0.43116, 0.43222, 0.43327,
    0.43434, 0.43540, 0.43647, 0.43754, 0.43862, 0.43970, 0.44077, 0.44186,
    0.44295, 0.44404, 0.44514, 0.44624, 0.44734, 0.44845, 0.44956, 0.45068,
    0.45179, 0.45291, 0.45404, 0.45516, 0.45630, 0.45744, 0.45858, 0.45972,
    0.46086, 0.46202, 0.46318, 0.46433, 0.46550, 0.46667, 0.46784, 0.46901,
    0.47019, 0.47137, 0.47256, 0.47375, 0.47495, 0.47615, 0.47735, 0.47856,
    0.47977, 0.48099, 0.48222, 0.48344, 0.48467, 0.48590, 0.48714, 0.48838,
    0.48963, 0.49088, 0.49213, 0.49340, 0.49466, 0.49593, 0.49721, 0.49849,
    0.49977, 0.50106, 0.50236, 0.50366, 0.50496, 0.50627, 0.50758, 0.50890,
    0.51023, 0.51155, 0.51289, 0.51422, 0.51556, 0.51692, 0.51827, 0.51964,
    0.52100, 0.52237, 0.52374, 0.52512, 0.52651, 0.52790, 0.52930, 0.53070,
    0.53212, 0.53353, 0.53495, 0.53638, 0.53781, 0.53925, 0.54070, 0.54214,
    0.54360, 0.54506, 0.54653, 0.54800, 0.54949, 0.55098, 0.55247, 0.55396,
    0.55548, 0.55699, 0.55851, 0.56003, 0.56156, 0.56310, 0.56464, 0.56621,
    0.56777, 0.56933, 0.57091, 0.57248, 0.57407, 0.57568, 0.57727, 0.57888,
    0.58050, 0.58213, 0.58376, 0.58541, 0.58705, 0.58871, 0.59037, 0.59204,
    0.59373, 0.59541, 0.59712, 0.59882, 0.60052, 0.60226, 0.60399, 0.60572,
    0.60748, 0.60922, 0.61099, 0.61276, 0.61455, 0.61635, 0.61814, 0.61996,
    0.62178, 0.62361, 0.62545, 0.62730, 0.62917, 0.63104, 0.63291, 0.63480,
    0.63671, 0.63862, 0.64054, 0.64249, 0.64443, 0.64638, 0.64835, 0.65033,
    0.65232, 0.65433, 0.65633, 0.65836, 0.66041, 0.66245, 0.66452, 0.66660,
    0.66868, 0.67078, 0.67290, 0.67503, 0.67717, 0.67932, 0.68151, 0.68368,
    0.68587, 0.68809, 0.69033, 0.69257, 0.69482, 0.69709, 0.69939, 0.70169,
    0.70402, 0.70634, 0.70869, 0.71107, 0.71346, 0.71587, 0.71829, 0.72073,
    0.72320, 0.72567, 0.72818, 0.73069, 0.73323, 0.73579, 0.73838, 0.74098,
    0.74360, 0.74622, 0.74890, 0.75159, 0.75429, 0.75704, 0.75979, 0.76257,
    0.76537, 0.76821, 0.77109, 0.77396, 0.77688, 0.77982, 0.78278, 0.78579,
    0.78883, 0.79187, 0.79498, 0.79809, 0.80127, 0.80445, 0.80767, 0.81095,
    0.81424, 0.81757, 0.82094, 0.82438, 0.82782, 0.83133, 0.83488, 0.83847,
    0.84210, 0.84577, 0.84951, 0.85328, 0.85713, 0.86103, 0.86499, 0.86900,
    0.87306, 0.87720, 0.88139, 0.88566, 0.89000, 0.89442, 0.89891, 0.90350,
    0.90818, 0.91295, 0.91780, 0.92272, 0.92780, 0.93299, 0.93828, 0.94369,
    0.94926, 0.95493, 0.96082, 0.96684, 0.97305, 0.97943, 0.98605, 0.99291,
    1.00000,
], dtype=np.float64)


def acr3_inverse(x):
    """
    Apply the inverse of ACR's default tone curve (vectorized).

    Uses the 1025-entry inverse LUT from the DNG SDK with linear
    interpolation, matching the C++ implementation exactly.
    """
    x = np.asarray(x, dtype=np.float64)
    x = np.clip(x, 0.0, 1.0)
    table_size = len(ACR3_INVERSE_TABLE)
    y = x * (table_size - 1)
    idx = np.clip(np.floor(y).astype(np.int32), 0, table_size - 2)
    frac = y - idx
    return ACR3_INVERSE_TABLE[idx] * (1.0 - frac) + ACR3_INVERSE_TABLE[idx + 1] * frac


# Display names for film simulations
DISPLAY_NAMES = {
    "ETERNA":         "ETERNA",
    "PROVIA":         "PROVIA",
    "Velvia":         "Velvia",
    "ASTIA":          "ASTIA",
    "CLASSIC-CHROME": "CLASSIC CHROME",
    "REALA-ACE":      "REALA ACE",
    "PRO-Neg.Std":    "PRO Neg.Std",
    "CLASSIC-Neg.":   "CLASSIC Neg.",
    "ETERNA-BB":      "ETERNA BLEACH BYPASS",
    "ACROS":          "ACROS",
}


# =============================================================================
# Base-85 Encoding
# =============================================================================

def b85_encode(data: bytes) -> str:
    """
    Encode binary data using Adobe's custom base-85 encoding.

    This is NOT standard Z85 or Ascii85. Key differences:
    - Little-endian uint32 grouping (Z85 uses big-endian)
    - Custom 85-character table safe for XML attributes
    - LSB-first digit ordering
    """
    n = len(data)
    total_chars = (n * 5 + 3) // 4
    padded = data + b'\x00' * ((-n) % 4)
    result = bytearray()
    for i in range(0, len(padded), 4):
        x = struct.unpack_from('<I', padded, i)[0]
        for _ in range(5):
            result.append(B85_TABLE[x % 85])
            x //= 85
    return result[:total_chars].decode('ascii')


# =============================================================================
# Binary Blob Construction
# =============================================================================

def build_binary_blob(lut_data, size):
    """
    Build the uncompressed binary blob for an ACR Creative Profile.

    Binary format (reverse-engineered from DNG SDK / XMPconverter):
      Header:  4 x uint32 LE  [1, 1, 3, size]
      LUT:     size^3 x 3 x uint16 LE  (delta from identity)
      Footer:  3 x uint32 LE + 2 x float64 LE
               [colors, gamma, gamut, min_range, max_range]

    LUT data is stored with B varying fastest, G middle, R slowest
    (opposite of .cube order). Values are delta-encoded: each sample
    stores (absolute_value - identity_value) as unsigned 16-bit wrapping.

    Parameters
    ----------
    lut_data : ndarray, shape (size^3, 3), float64
        LUT output values in [0, 1], R-fastest ordering (standard .cube).
    size : int
        Grid size (must be 32 for ACR Creative Profiles).
    """
    # Header
    header = struct.pack('<IIII', 1, 1, 3, size)

    # Identity (nop) values for each grid index
    # Formula from DNG SDK: (index * 0xFFFF + (size >> 1)) / (size - 1)
    nop = np.array(
        [(i * 0xFFFF + (size >> 1)) // (size - 1) for i in range(size)],
        dtype=np.int32,
    )

    # Reorder from R-fastest (.cube) to B-fastest (ACR binary)
    # .cube flat index: bIdx*N^2 + gIdx*N + rIdx  (R fastest)
    # ACR binary index: rIdx*N^2 + gIdx*N + bIdx  (B fastest)
    cube = lut_data.reshape(size, size, size, 3)  # (B, G, R, 3)
    reordered = cube.transpose(2, 1, 0, 3)         # (R, G, B, 3)

    # Convert to absolute uint16 values
    abs_vals = np.round(reordered * 65535).astype(np.int32)

    # Compute deltas from identity (unsigned wrapping)
    nop_r = nop.reshape(size, 1, 1)
    nop_g = nop.reshape(1, size, 1)
    nop_b = nop.reshape(1, 1, size)
    deltas = np.stack([
        (abs_vals[:, :, :, 0] - nop_r) & 0xFFFF,
        (abs_vals[:, :, :, 1] - nop_g) & 0xFFFF,
        (abs_vals[:, :, :, 2] - nop_b) & 0xFFFF,
    ], axis=-1)

    # Pack as little-endian uint16
    lut_bytes = deltas.reshape(-1).astype('<u2').tobytes()

    # Footer
    footer = struct.pack('<III', COLORS_PROPHOTO, GAMMA_PROPHOTO, GAMUT_CLIP)
    footer += struct.pack('<dd', 0.0, 2.0)  # Amount slider range: 0% to 200%

    return header + lut_bytes + footer


# =============================================================================
# XMP Assembly
# =============================================================================

XMP_TEMPLATE = """\
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Adobe XMP Core 7.0-c000 1.000000, 0000/00/00-00:00:00        ">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"
   crs:PresetType="Look"
   crs:Cluster=""
   crs:UUID="{uuid}"
   crs:SupportsAmount="True"
   crs:SupportsColor="True"
   crs:SupportsMonochrome="True"
   crs:SupportsHighDynamicRange="True"
   crs:SupportsNormalDynamicRange="True"
   crs:SupportsSceneReferred="True"
   crs:SupportsOutputReferred="True"
   crs:RequiresRGBTables="False"
   crs:CameraModelRestriction=""
   crs:Copyright=""
   crs:ContactInfo=""
   crs:Version="14.3"
   crs:ProcessVersion="11.0"
   crs:ConvertToGrayscale="False"
   crs:RGBTable="{md5}"
   crs:Table_{md5}="{b85_data}"
   crs:HasSettings="True">
   <crs:Name>
    <rdf:Alt>
     <rdf:li xml:lang="x-default">{title}</rdf:li>
    </rdf:Alt>
   </crs:Name>
   <crs:ShortName>
    <rdf:Alt>
     <rdf:li xml:lang="x-default"/>
    </rdf:Alt>
   </crs:ShortName>
   <crs:SortName>
    <rdf:Alt>
     <rdf:li xml:lang="x-default"/>
    </rdf:Alt>
   </crs:SortName>
   <crs:Group>
    <rdf:Alt>
     <rdf:li xml:lang="x-default"{group_elem}
    </rdf:Alt>
   </crs:Group>
   <crs:Description>
    <rdf:Alt>
     <rdf:li xml:lang="x-default"/>
    </rdf:Alt>
   </crs:Description>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
"""


def generate_profile(lut_data, size, title, group):
    """
    Generate a complete .xmp Creative Profile from LUT data.

    Returns the XMP file content as a string.
    """
    # Build binary blob
    blob = build_binary_blob(lut_data, size)

    # MD5 of raw blob (uppercase hex) — used as Table_ key and RGBTable ref
    md5_hex = hashlib.md5(blob).hexdigest().upper()

    # UUID = MD5(md5_hex + unix_timestamp)
    uuid_hex = hashlib.md5(
        (md5_hex + str(int(time.time()))).encode('ascii')
    ).hexdigest().upper()

    # Compress with zlib (default level 6) and prepend uncompressed size
    compressed = zlib.compress(blob, 6)
    payload = struct.pack('<I', len(blob)) + compressed

    # Base-85 encode
    b85_data = b85_encode(payload)

    # Group element
    group_elem = f">{group}</rdf:li>" if group else "/>"

    return XMP_TEMPLATE.format(
        uuid=uuid_hex,
        md5=md5_hex,
        b85_data=b85_data,
        title=title,
        group_elem=group_elem,
    )


# =============================================================================
# Main
# =============================================================================

def main():
    print("Fujifilm Film Simulation Creative Profile Generator")
    print("=" * 60)

    # Compute conversion matrices (same as generate_luts.py ProPhoto variant)
    M_prophoto_to_fgamutc = conversion_matrix("ProPhoto", "F-Gamut C")
    M_bt709_to_prophoto = conversion_matrix("BT.709", "ProPhoto")

    # The Creative Profile LUT receives data that has been:
    #   1. Demosaiced and color-corrected (linear ProPhoto RGB)
    #   2. Tone-curved by ACR's default S-curve (still linear ProPhoto)
    #   3. Gamma 1.8 encoded (to match our declared LUT input space)
    #
    # Our input_decode reverses steps 3 and 2, then applies an exposure
    # offset to match ACR's default brightness level:
    #   gamma 1.8 decode → inverse ACR3 curve → exposure boost → scene-linear
    # Then the rest of the pipeline (matrix → F-Log2C → Fujifilm LUT)
    # applies only the Fujifilm film simulation's own tone curve.
    exposure_gain = 2.0 ** EXPOSURE_OFFSET_STOPS
    variant = {
        "name": "ProPhoto",
        "matrix_in": M_prophoto_to_fgamutc,
        "input_decode": lambda x: acr3_inverse(gamma_decode(x, 1.8)) * exposure_gain,
        "matrix_out": M_bt709_to_prophoto,
        "output_gamma": 2.2,
        "output_encode": lambda x: gamma_encode(x, 1.8),
    }

    group = "Fujifilm"
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    count = 0

    for src_filename, sim_name in FILM_SIMS:
        src_path = os.path.join(SOURCE_DIR, src_filename)
        print(f"\nReading source LUT: {src_filename}")
        src_size, src_data = read_cube(src_path)

        # Generate 32-grid ProPhoto RGB (gamma 1.8) LUT
        print(f"  Generating {GRID_SIZE}-grid ProPhoto LUT...")
        lut_data = process_variant(
            src_data, src_size, variant, grid_size=GRID_SIZE
        )

        # Build profile
        display_name = DISPLAY_NAMES.get(sim_name, sim_name)
        title = f"Fujifilm {display_name}"
        xmp = generate_profile(lut_data, GRID_SIZE, title, group)

        # Write .xmp file
        filename = f"Fujifilm {sim_name}.xmp"
        filepath = os.path.join(OUTPUT_DIR, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(xmp)

        count += 1
        print(f"  -> {filename} ({len(xmp):,} bytes)")

    print(f"\nDone! Generated {count} profiles in: {OUTPUT_DIR}")

    # Run verification
    verify()

    print(f"\nTo install, copy the .xmp files to:")
    print(f"  macOS:   ~/Library/Application Support/Adobe/CameraRaw/Settings/")
    print(f"  Windows: %APPDATA%\\Adobe\\CameraRaw\\Settings\\")
    print(f"Then restart Lightroom / Photoshop.")
    print("=" * 60)


# =============================================================================
# Verification
# =============================================================================

def b85_decode(s):
    """Decode Adobe's custom base-85 encoding (inverse of b85_encode)."""
    decode_map = {c: i for i, c in enumerate(B85_TABLE)}
    data = s.encode('ascii')
    total_bytes = (len(data) * 4) // 5
    padded = data + bytes([B85_TABLE[0]] * ((-len(data)) % 5))
    result = bytearray()
    for i in range(0, len(padded), 5):
        x = sum(decode_map[padded[i + j]] * (85 ** j) for j in range(5))
        result.extend(struct.pack('<I', x & 0xFFFFFFFF))
    return bytes(result[:total_bytes])


def verify():
    """Verify generated profiles: encoding round-trip, binary structure, LUT data."""
    import xml.etree.ElementTree as ET
    import re

    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    # 1. ACR3 inverse curve
    print("\n1. ACR3 inverse curve...")
    assert len(ACR3_INVERSE_TABLE) == 1025, \
        f"Expected 1025 entries, got {len(ACR3_INVERSE_TABLE)}"
    assert ACR3_INVERSE_TABLE[0] == 0.0 and ACR3_INVERSE_TABLE[-1] == 1.0, \
        "Endpoints must be 0 and 1"
    assert np.all(np.diff(ACR3_INVERSE_TABLE) > 0), "Table must be monotonic"
    # 18% gray: ACR3 forward maps ~0.18 to ~0.39, so inv(0.39) ≈ 0.18
    assert abs(float(acr3_inverse(0.39)) - 0.18) < 0.002, "18% gray round-trip"
    print("   PASS (1025 entries, monotonic, 18% gray round-trips)")

    # 2. Base-85 round-trip
    print("\n2. Base-85 round-trip...")
    for length in [1, 2, 3, 4, 5, 16, 100, 1000]:
        data = bytes(np.random.default_rng(42).integers(0, 256, length, dtype=np.uint8))
        assert b85_decode(b85_encode(data)) == data, f"Failed at length {length}"
    print("   PASS (all lengths)")

    # 3. Parse a generated profile
    print("\n3. XMP structure and binary blob...")
    provia_path = os.path.join(OUTPUT_DIR, "Fujifilm PROVIA.xmp")
    with open(provia_path, 'r') as f:
        xmp_content = f.read()

    # Valid XML
    ET.fromstring(xmp_content)

    # Extract base-85 data
    m = re.search(r'crs:Table_([A-F0-9]+)="([^"]+)"', xmp_content)
    md5_in_tag = m.group(1)
    b85_str = m.group(2)

    # Also check RGBTable references the same MD5
    m2 = re.search(r'crs:RGBTable="([^"]+)"', xmp_content)
    assert m2.group(1) == md5_in_tag, "RGBTable must reference Table_ MD5"

    # Decode and decompress
    payload = b85_decode(b85_str)
    uncomp_size = struct.unpack('<I', payload[:4])[0]
    blob = zlib.decompress(payload[4:])
    assert len(blob) == uncomp_size, "Uncompressed size mismatch"

    # Verify MD5
    assert hashlib.md5(blob).hexdigest().upper() == md5_in_tag, "MD5 mismatch"

    # Check header
    h1, h2, ch, sz = struct.unpack('<IIII', blob[:16])
    assert (h1, h2, ch, sz) == (1, 1, 3, GRID_SIZE), \
        f"Header mismatch: got ({h1},{h2},{ch},{sz})"

    # Check footer
    expected_blob_size = 16 + GRID_SIZE**3 * 3 * 2 + 28
    assert len(blob) == expected_blob_size, \
        f"Blob size {len(blob)} != expected {expected_blob_size}"
    footer_off = 16 + GRID_SIZE**3 * 3 * 2
    colors, gamma, gamut = struct.unpack('<III', blob[footer_off:footer_off+12])
    min_r, max_r = struct.unpack('<dd', blob[footer_off+12:footer_off+28])
    assert (colors, gamma, gamut) == (COLORS_PROPHOTO, GAMMA_PROPHOTO, GAMUT_CLIP)
    assert (min_r, max_r) == (0.0, 2.0)

    print(f"   PASS (valid XML, MD5 verified, header=[1,1,3,{GRID_SIZE}], "
          f"footer=[ProPhoto,γ1.8,clip,0-200%])")

    # 4. LUT data reconstruction
    print("\n4. LUT data reconstruction...")
    lut_raw = np.frombuffer(blob[16:footer_off], dtype='<u2').reshape(
        GRID_SIZE, GRID_SIZE, GRID_SIZE, 3)
    nop = np.array(
        [(i * 0xFFFF + (GRID_SIZE >> 1)) // (GRID_SIZE - 1) for i in range(GRID_SIZE)],
        dtype=np.int32,
    )
    # Reconstruct absolute values
    abs_r = (lut_raw[:,:,:,0].astype(np.int32) + nop.reshape(GRID_SIZE,1,1)) & 0xFFFF
    abs_g = (lut_raw[:,:,:,1].astype(np.int32) + nop.reshape(1,GRID_SIZE,1)) & 0xFFFF
    abs_b = (lut_raw[:,:,:,2].astype(np.int32) + nop.reshape(1,1,GRID_SIZE)) & 0xFFFF

    # Black corner (r=0,g=0,b=0) — should be near 0
    black = (abs_r[0,0,0], abs_g[0,0,0], abs_b[0,0,0])
    assert all(v < 1000 for v in black), f"Black corner too high: {black}"

    # White corner (r=31,g=31,b=31) — should be well above 0
    n = GRID_SIZE - 1
    white = (abs_r[n,n,n], abs_g[n,n,n], abs_b[n,n,n])
    assert all(v > 30000 for v in white), f"White corner too low: {white}"

    # Gray neutrality at midpoint
    mid = GRID_SIZE // 2
    gray = np.array([abs_r[mid,mid,mid], abs_g[mid,mid,mid], abs_b[mid,mid,mid]])
    spread = int(gray.max() - gray.min())

    print(f"   Black (0,0,0):       R={black[0]:5d} G={black[1]:5d} B={black[2]:5d}")
    print(f"   White ({n},{n},{n}): R={white[0]:5d} G={white[1]:5d} B={white[2]:5d}")
    print(f"   Mid gray neutrality: spread={spread} (lower = better)")
    print("   PASS")

    # 5. All profiles exist and are valid XML
    print("\n5. All profiles...")
    for _, sim_name in FILM_SIMS:
        path = os.path.join(OUTPUT_DIR, f"Fujifilm {sim_name}.xmp")
        assert os.path.exists(path), f"Missing: {path}"
        with open(path) as f:
            ET.fromstring(f.read())
    print(f"   PASS (all {len(FILM_SIMS)} profiles exist and parse as valid XML)")


if __name__ == "__main__":
    main()
