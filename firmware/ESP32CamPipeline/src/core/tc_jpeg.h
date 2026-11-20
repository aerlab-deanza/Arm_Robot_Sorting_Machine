// Decodes a JPEG into plain RGB pixels. The AMB82-Mini only gives JPEG pictures to an
// Arduino sketch, so the board decodes each one before the pipeline looks at it.
// Uses the small TJpgDec decoder in third_party/tjpgd.
#pragma once

#include <stddef.h>
#include <stdint.h>

namespace tc {

// Decodes `jpeg` (length bytes) into `rgb` as packed RGB888 (3 bytes per pixel, rows
// one after another). `rgb_capacity` is how many bytes `rgb` can hold. `shrink` is 0, 1, 2
// or 3 to make the picture 1, 1/2, 1/4 or 1/8 as wide and as tall (smaller is faster).
// On success returns true and sets `width` and `height` of the decoded picture.
bool decode_jpeg(const uint8_t* jpeg, size_t length, uint8_t* rgb, size_t rgb_capacity, int shrink,
                 int& width, int& height);

}  // namespace tc
