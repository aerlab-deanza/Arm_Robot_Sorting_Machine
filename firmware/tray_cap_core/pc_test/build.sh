#!/bin/sh
# Builds the core for the PC, to test it against the Python pipeline.
# Run from anywhere:  sh firmware/tray_cap_core/pc_test/build.sh
cd "$(dirname "$0")" || exit 1
gcc -O2 -c -o tjpgd.o ../third_party/tjpgd/tjpgd.c || exit 1
g++ -std=c++17 -O2 -Wall -Wextra -o pc_test pc_test.cpp ../tc_image.cpp ../tc_tray.cpp ../tc_caps.cpp \
    ../tc_pipeline.cpp ../tc_jpeg.cpp tjpgd.o
rm -f tjpgd.o
