#! /usr/bin/env python                                                                                   

import argparse
import json
import sys, os
import evaluate

debugFlag = False

def debug(msg):
    if debugFlag:
        print(f'{msg}', file=sys.stderr)


def getListFromFile(f):
    resL = []
    with open(f, "r") as fp:
        for line in fp:
            hyp = line.strip()
            resL.append(hyp)
    return resL


def main():
    global debugFlag
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--debug", action="store_true")
    parser.add_argument("hypFile")
    parser.add_argument("refFile")
    args = parser.parse_args()

    if args.debug:
        debugFlag = True
    hypFile = args.hypFile
    refFile = args.refFile
    hypList = getListFromFile(hypFile)
    refList = getListFromFile(refFile)
    debug(f'found {len(hypList)} hyp from {hypFile}')
    debug(f'found {len(refList)} ref from {refFile}')

    exact_match = evaluate.load("exact_match")

    score = exact_match.compute(references=refList, predictions=hypList,
                                ignore_case=True, ignore_punctuation=True)

    debug(f'score {score}')
    print(json.dumps(score))

            
if __name__ == "__main__":
    main()
