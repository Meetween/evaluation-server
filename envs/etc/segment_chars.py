#! /usr/bin/env python3

import sys

for line in sys.stdin:
    line = " ".join(line.rstrip())
    print(line)

