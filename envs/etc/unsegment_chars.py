#! /usr/bin/env python3

import sys
import re

for line in sys.stdin:
    line = re.sub(r'(.)\s', r'\1', line)
    print(line)

