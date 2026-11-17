#!/usr/bin/env python3

import argparse
import json
import sys
from statistics import fmean

import evaluate


debugFlag = False
allscoresFlag = False


def debug(msg):
    if debugFlag:
        print(msg, file=sys.stderr)


def getListFromFile(f):
    resL = []
    with open(f, "r") as fp:
        for line in fp:
            # Keep one response per line.
            # Empty responses are kept as empty strings so that
            # hypothesis/reference alignment is preserved.
            resL.append(line.strip())
    return resL


def main():
    global debugFlag, allscoresFlag

    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--all", action="store_true")
    parser.add_argument("-d", "--debug", action="store_true")
    parser.add_argument(
        "-l",
        "--lang",
        default="en",
        help="Language code used by BERTScore (default: en)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=16,
        help="BERTScore batch size (default: 16)",
    )
    parser.add_argument("hypFile")
    parser.add_argument("refFile")

    args = parser.parse_args()

    if args.all:
        allscoresFlag = True
    if args.debug:
        debugFlag = True

    hypList = getListFromFile(args.hypFile)
    refList = getListFromFile(args.refFile)

    debug(f"found {len(hypList)} hyp from {args.hypFile}")
    debug(f"found {len(refList)} ref from {args.refFile}")

    try:
        if len(hypList) != len(refList):
            raise ValueError(
                f"Different number of predictions ({len(hypList)}) "
                f"and references ({len(refList)})"
            )

        if len(hypList) == 0:
            raise ValueError("Input files are empty")

        bertscore_metric = evaluate.load("bertscore")

        scores = bertscore_metric.compute(
            predictions=hypList,
            references=refList,
            lang=args.lang,
            rescale_with_baseline=True,
            batch_size=args.batch_size,
        )

        # HF BERTScore returns one score per example.
        # Compute corpus-level averages.
        precision = fmean(scores["precision"])
        recall = fmean(scores["recall"])
        f1 = fmean(scores["f1"])

        scores = {"bertscore": f1}
        if allscoresFlag:
            scores["precision"] = precision
            scores["recall"] = recall  
            
        debug(f"scores {scores}")

        print(json.dumps({
            "state": "OK",
            "scores": scores
        }))
    except Exception as e:  # noqa
        print(json.dumps({
            "state": "ERROR",
            "reason": str(e),
            "scores": {}
        }))


if __name__ == "__main__":
    main()
