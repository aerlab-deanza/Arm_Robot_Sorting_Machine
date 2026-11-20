#include "tc_jpeg.h"

extern "C" {
#include "third_party/tjpgd/tjpgd.h"
}

namespace tc {

namespace {

struct Source {
  const uint8_t* data;
  size_t length;
  size_t position;
  uint8_t* rgb;
  size_t capacity;
  int width;   // decoded picture size
  int height;
  bool too_small;
};

size_t read_jpeg(JDEC* decoder, uint8_t* buffer, size_t wanted) {
  Source* source = (Source*)decoder->device;
  const size_t left = source->length - source->position;
  const size_t count = wanted < left ? wanted : left;
  if (buffer) {
    for (size_t i = 0; i < count; i++) buffer[i] = source->data[source->position + i];
  }
  source->position += count;
  return count;
}

// TJpgDec hands over the picture a block at a time (RGB888, with JD_FORMAT 0).
int write_block(JDEC* decoder, void* bitmap, JRECT* rect) {
  Source* source = (Source*)decoder->device;
  const uint8_t* pixels = (const uint8_t*)bitmap;
  const int block_w = rect->right - rect->left + 1;
  for (int y = rect->top; y <= rect->bottom; y++) {
    uint8_t* row = source->rgb + ((size_t)y * source->width + rect->left) * 3;
    const uint8_t* from = pixels + (size_t)(y - rect->top) * block_w * 3;
    for (int i = 0; i < block_w * 3; i++) row[i] = from[i];
  }
  return 1;  // keep going
}

}  // namespace

bool decode_jpeg(const uint8_t* jpeg, size_t length, uint8_t* rgb, size_t rgb_capacity, int shrink,
                 int& width, int& height) {
  static uint8_t work[TJPGD_WORKSPACE_SIZE + 256];  // TJpgDec's working memory
  JDEC decoder;
  Source source = {jpeg, length, 0, rgb, rgb_capacity, 0, 0, false};
  if (jd_prepare(&decoder, read_jpeg, work, sizeof(work), &source) != JDR_OK) return false;
  if (shrink < 0) shrink = 0;
  if (shrink > 3) shrink = 3;
  source.width = decoder.width >> shrink;
  source.height = decoder.height >> shrink;
  if ((size_t)source.width * source.height * 3 > rgb_capacity) return false;
  if (jd_decomp(&decoder, write_block, (uint8_t)shrink) != JDR_OK) return false;
  width = source.width;
  height = source.height;
  return true;
}

}  // namespace tc
