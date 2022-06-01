import numpy as np
from numba import njit, prange


def add_lastframe_padding(arr: np.ndarray, res: tuple[int, int], bpp: int) -> np.ndarray:
    framesize = int(res[0] * res[1] / 8 * bpp)
    last_frame_padding = framesize - (arr.size % framesize)
    if last_frame_padding:
        arr = np.append(arr, np.zeros(last_frame_padding, dtype=np.uint8))
    return arr


@njit('void(uint8[::1], uint8[::1], uint8[::1])', inline='never')
def _numba_transform_bpp3_x64(arr, out, mapping):
    for i in range(64):
        j = i * 3
        out[i] = mapping[(arr[j]<<2)|(arr[j+1]<<1)|(arr[j+2])]


@njit('void(uint8[::1], int_, uint8[::1], uint8[::1])', parallel=True)
def _numba_transform_bpp3(arr, div, out, mapping):
    for i in prange(div//64):
        _numba_transform_bpp3_x64(arr[i*192:(i*192)+192], out[i*64:(i*64)+64], mapping)


@njit('void(uint8[::1], uint8[::1], uint8[::1])', inline='never')
def _numba_transform_bpp2_x64(arr, out, mapping):
    for i in range(64):
        j = i * 2
        out[i] = mapping[(arr[j]<<1)|(arr[j+1])]


@njit('void(uint8[::1], int_, uint8[::1], uint8[::1])', parallel=True)
#! remove the loop unrolling, div, mapping, floor division, and all the bloat that is unnecessary. Also, it should be tested again if this benefits from parallelism, because i doubt it.
#! should prob be done when i make (made) the tests for it to verify we did not break everything.
def _numba_transform_bpp2(arr, div, out, mapping):
    for i in prange(div//64):
        _numba_transform_bpp2_x64(arr[i*128:(i*128)+128], out[i*64:(i*64)+64], mapping)


def transform_array(arr: np.ndarray, bpp: int) -> np.ndarray:
    """Transforms a uint8 numpy array (0, 255, 38, ..) representing individual bytes
    into a uint8 numpy array representing 8 bit greyscale pixels. Returns a new array.
    The output depends on the 'bpp' (or 'bits per pixel') parameter.

    A 'bpp' of 1 for example, dictates each pixel should hold the information of 
    a single bit. A bit has 2 possible states, 1 and 0, so our corresponding pixel
    should too. The pixel will be either 0 or 255 (black and white) to represent
    0 and 1 respectively.

    A 'bpp' of 3 thus means 3 bits of information in every pixel.
    Since 3 bits have 8 possible combinations (000,001,010,011,100,101,110,111),
    our pixel will need 8 distinct states as well (0,48,80,112,144,176,208,255) 
    to represent the 3 bits.

    It does this by first unpacking the array into a binary representation of it
    (essentially converting from decimal to binary, 65 -> 01000001).
    It then groups consecutive binary digits into groups of 3, before mapping
    these triplets to an appropriate pixel value.

    This function expects the length of the input array to be divisible, without
    remainder, by the bpp as well as bpp*8.
    This works on products of the pixel sum of common resolutions (1080,720p,4k...),
    so long as padding for the last frame was added to the array before transforming it,
    this requirement will be satisfied.
    """
    if arr.size % bpp:
        raise ValueError(f'The length of the given array ({arr.size}) is not divisible by the given bpp ({bpp}).')
    if arr.size % (bpp*8):
        raise ValueError(f'The length of the given array ({arr.size}) is not divisible by the given bpp * 8 ({(bpp*8)}).')
    arr = np.unpackbits(arr)
    div = int(arr.size / bpp)
    out = np.zeros(div, dtype=np.uint8)
    if bpp == 1:
        mapping = np.array([0,255], dtype=np.uint8)
        out = mapping[arr]
    elif bpp == 2:
        mapping = np.array([0,96,160,255], dtype=np.uint8)
        _numba_transform_bpp2(arr, div, out, mapping)
    elif bpp == 3:
        mapping = np.array([0,48,80,112,144,176,208,255], dtype=np.uint8)
        _numba_transform_bpp3(arr, div, out, mapping)
    elif bpp == 8:
        raise ValueError('A bpp of 8 was passed as argument. No transformation is required when using a bpp of 8.')
    else: # should probably be inn api class not here cause well have it twice then
        raise ValueError(f'Unsupported bpp argument: {bpp} of type {type(bpp)}.')
    return out