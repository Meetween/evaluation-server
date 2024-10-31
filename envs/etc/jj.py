#! /usr/bin/env python3

# join json files provided as arguments

import sys
import json
import ast

joinedD = dict()
for f in sys.argv[1:]:
  ## print(f'{f}')
  with open(f, 'r') as fp:
    data = json.load(fp)
    joinedD.update(data)

## outD = json.dumps(joinedD)
## print(f'{type(outD)} {outD}')
## outD = ast.literal_eval(json.dumps(joinedD))
## print(f'{type(outD)} {outD}')

outD = json.dumps(joinedD)
print(f'{outD}')

