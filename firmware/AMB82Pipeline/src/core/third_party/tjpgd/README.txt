TJpgDec - Tiny JPEG Decompressor R0.03, (C) 2021 ChaN. Source: https://github.com/Bodmer/TJpg_Decoder (src/).
License (from the top of tjpgd.c): free to use, modify and redistribute, including in commercial products,
under your own responsibility, with NO WARRANTY. Redistributions of source code must keep the copyright notice.

Our only change: in tjpgdcnf.h, JD_FORMAT is 0 (the decoder outputs RGB888, 3 bytes per pixel) instead of 1 (RGB565).
