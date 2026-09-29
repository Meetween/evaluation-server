import argparse
import json
import re
import string
import sys


if __name__ == "__main__":
    debugInfo = False
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--debug", help="increase output verbosity",
                        action="store_true")
    parser.add_argument("input_hyp_json_file")
    parser.add_argument("input_ref_json_file")
    parser.add_argument("output_hyp_txt_file")
    parser.add_argument("output_ref_txt_file")
    args = parser.parse_args()
    if args.debug:
        debugInfo = True
    if debugInfo:
       print(f'ARGS: {args.input_hyp_json_file} {args.input_ref_json_file} {args.output_hyp_txt_file} {args.output_ref_txt_file}')
    with open(args.input_hyp_json_file) as f:
        hypDict = json.load(f)
    with open(args.input_ref_json_file) as f:
        refDict = json.load(f)

    if debugInfo:
       print(f'original dicts hypDict {len(hypDict)}, refDict {len(refDict)}', file=sys.stderr)

    hypList, refList = [], []
    for article in refDict["data"]:
        for par in article["paragraphs"]:
            for qa in par["qas"]:
                id = qa["id"]
                answer = qa["answers"][0]["text"]
                hypList.append(hypDict[id])
                refList.append(answer)

    if debugInfo:
       print(f'found hypList {len(hypList)}, refList {len(refList)}', file=sys.stderr)

    with open(args.output_hyp_txt_file, mode='w') as f:
        for item in hypList:
            print(item, file=f)
    with open(args.output_ref_txt_file, mode='w') as f:
        for item in refList:
            print(item, file=f)

    sys.exit(0)



