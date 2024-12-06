#! /usr/bin/env python

import sys
import json
import statistics

# get mean and standard deviation of a number population in standard input
# (any number of numbers for each line) 
#
scoreList = []
for line in sys.stdin:
  items = line.split()
  for n in items:
    scoreList.append(float(n))

mean  = statistics.mean(scoreList)
stdev = statistics.pstdev(scoreList)

print(f'{mean} {stdev}')



