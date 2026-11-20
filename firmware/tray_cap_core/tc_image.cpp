#include "tc_image.h"

#include <string.h>

namespace tc {

namespace {

// For each pixel: does any (mode 0) or does every (mode 1) pixel inside the
// window of +-radius on one line equal white? Uses a running count, so the
// time does not depend on the radius. Outside the picture counts as black for
// "any" and is ignored for "every", like OpenCV.
void line_filter(const uint8_t* in, uint8_t* out, int length, int step, int radius, bool every) {
  int count = 0;
  for (int i = 0; i <= radius && i < length; i++) count += in[i * step] ? 1 : 0;
  for (int x = 0; x < length; x++) {
    const int lo = x - radius < 0 ? 0 : x - radius;
    const int hi = x + radius >= length ? length - 1 : x + radius;
    const int window = hi - lo + 1;
    out[x * step] = (every ? (count == window) : (count > 0)) ? 255 : 0;
    if (x - radius >= 0) count -= in[(x - radius) * step] ? 1 : 0;
    if (x + radius + 1 < length) count += in[(x + radius + 1) * step] ? 1 : 0;
  }
}

void box_filter(const uint8_t* in, uint8_t* out, uint8_t* tmp, int w, int h, int radius, bool every) {
  for (int y = 0; y < h; y++) line_filter(in + y * w, tmp + y * w, w, 1, radius, every);
  for (int x = 0; x < w; x++) line_filter(tmp + x, out + x, h, w, radius, every);
}

}  // namespace

void dilate(const uint8_t* in, uint8_t* out, uint8_t* tmp, int w, int h, int radius) {
  box_filter(in, out, tmp, w, h, radius, false);
}

void erode(const uint8_t* in, uint8_t* out, uint8_t* tmp, int w, int h, int radius) {
  box_filter(in, out, tmp, w, h, radius, true);
}

void close_mask(uint8_t* mask, uint8_t* scratch1, uint8_t* scratch2, int w, int h, int radius) {
  dilate(mask, scratch1, scratch2, w, h, radius);
  erode(scratch1, mask, scratch2, w, h, radius);
}

void open_mask(uint8_t* mask, uint8_t* scratch1, uint8_t* scratch2, int w, int h, int radius) {
  erode(mask, scratch1, scratch2, w, h, radius);
  dilate(scratch1, mask, scratch2, w, h, radius);
}

namespace {

constexpr int MAX_PROVISIONAL = (MAX_W > 320) ? 4096 : 2048;

int find_root(uint16_t* parent, int a) {
  while (parent[a] != a) {
    parent[a] = parent[parent[a]];
    a = parent[a];
  }
  return a;
}

void join(uint16_t* parent, int a, int b) {
  a = find_root(parent, a);
  b = find_root(parent, b);
  if (a == b) return;
  if (a < b) parent[b] = (uint16_t)a; else parent[a] = (uint16_t)b;
}

}  // namespace

// Working lists for find_blobs(). Big, so they live in the big memory (PSRAM on the ESP32),
// allocated once on first use.
struct BlobWork {
  uint16_t parent[MAX_PROVISIONAL];
  int final_id[MAX_PROVISIONAL];
  Blob all[MAX_PROVISIONAL];
  int order[MAX_PROVISIONAL];
  uint16_t renumber[MAX_PROVISIONAL];
};

int find_blobs(const uint8_t* mask, uint16_t* labels, int w, int h, Blob* blobs) {
  static BlobWork* work = nullptr;
  if (work == nullptr) work = (BlobWork*)alloc(sizeof(BlobWork));
  if (work == nullptr) return 0;
  uint16_t* parent = work->parent;
  int next = 1;
  parent[0] = 0;
  // Pass 1: give every white pixel a provisional number, and note which numbers touch.
  for (int y = 0; y < h; y++) {
    for (int x = 0; x < w; x++) {
      const int i = y * w + x;
      if (!mask[i]) {
        labels[i] = 0;
        continue;
      }
      int neighbors[4];
      int n = 0;
      if (x > 0 && labels[i - 1]) neighbors[n++] = labels[i - 1];
      if (y > 0) {
        if (x > 0 && labels[i - w - 1]) neighbors[n++] = labels[i - w - 1];
        if (labels[i - w]) neighbors[n++] = labels[i - w];
        if (x < w - 1 && labels[i - w + 1]) neighbors[n++] = labels[i - w + 1];
      }
      if (n == 0) {
        if (next < MAX_PROVISIONAL) {
          parent[next] = (uint16_t)next;
          labels[i] = (uint16_t)next++;
        } else {
          labels[i] = (uint16_t)(MAX_PROVISIONAL - 1);  // too many: merge into the last one
        }
      } else {
        int smallest = neighbors[0];
        for (int k = 1; k < n; k++) if (neighbors[k] < smallest) smallest = neighbors[k];
        labels[i] = (uint16_t)smallest;
        for (int k = 0; k < n; k++) join(parent, smallest, neighbors[k]);
      }
    }
  }
  // Pass 2: one final number per blob, and its statistics.
  int* final_id = work->final_id;
  Blob* all = work->all;
  int count = 0;
  for (int i = 0; i < next; i++) final_id[i] = 0;
  for (int y = 0; y < h; y++) {
    for (int x = 0; x < w; x++) {
      const int i = y * w + x;
      if (!labels[i]) continue;
      const int root = find_root(parent, labels[i]);
      if (!final_id[root]) {
        final_id[root] = ++count;
        Blob& b = all[count];
        b.area = 0;
        b.min_x = w; b.min_y = h; b.max_x = -1; b.max_y = -1;
        b.sum_x = 0; b.sum_y = 0;
      }
      Blob& b = all[final_id[root]];
      b.area++;
      b.sum_x += x; b.sum_y += y;
      if (x < b.min_x) b.min_x = x;
      if (x > b.max_x) b.max_x = x;
      if (y < b.min_y) b.min_y = y;
      if (y > b.max_y) b.max_y = y;
      labels[i] = (uint16_t)final_id[root];
    }
  }
  // Keep the biggest MAX_BLOBS blobs, and renumber so labels[] matches blobs[].
  int* order = work->order;
  for (int i = 1; i <= count; i++) order[i - 1] = i;
  const int keep = count < MAX_BLOBS ? count : MAX_BLOBS;
  for (int i = 0; i < keep; i++) {  // selection sort: only the top `keep` matter
    int best = i;
    for (int j = i + 1; j < count; j++) if (all[order[j]].area > all[order[best]].area) best = j;
    const int tmp = order[i]; order[i] = order[best]; order[best] = tmp;
  }
  uint16_t* renumber = work->renumber;
  for (int i = 0; i <= count; i++) renumber[i] = 0;
  for (int i = 0; i < keep; i++) {
    renumber[order[i]] = (uint16_t)(i + 1);
    blobs[i + 1] = all[order[i]];
  }
  for (int i = 0; i < w * h; i++) labels[i] = renumber[labels[i]];
  return keep;
}

}  // namespace tc
