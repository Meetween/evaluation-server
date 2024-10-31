#! /usr/bin/env python 

import jiwer
import argparse
import sys

debugFlag = False

parser = argparse.ArgumentParser()
# (optional) args
parser.add_argument("-d", "--debug", action="store_true", help="enable debug")
#
# positional (mandatory) args
parser.add_argument("lang", help="the language (2-chars code) of hyp an ref")
parser.add_argument("hypFile", help="the hyp file to be evaluated")
parser.add_argument("refFile", help="the reference file")

args = parser.parse_args()
lang    = args.lang
hypFile = args.hypFile
refFile = args.refFile
if args.debug:
    debugFlag    = args.debug

with open(hypFile, 'r') as fd:
    hypStr = fd.read()
with open(refFile, 'r') as fd:
    refStr = fd.read()

if debugFlag:
    print(f'{hypStr}\n=============\n{refStr}', file=sys.stderr)
wer = jiwer.wer(refStr, hypStr)
print('{"wer": ' + f'{wer*100:.2f}' + '}')



