#!/usr/bin/env python3                                                                                         

import argparse
import json
import sys


def create_jsonl(source_path, hypothesis_path, reference_path, output_path="output.jsonl"):
    with open(source_path, 'r', encoding='utf-8') as src_file, \
         open(hypothesis_path, 'r', encoding='utf-8') as hyp_file, \
         open(reference_path, 'r', encoding='utf-8') as ref_file, \
         open(output_path, 'w', encoding='utf-8') as out_file:
        for src_line, hyp_line, ref_line in zip(src_file, hyp_file, ref_file):
            entry = {
                "source": src_line.strip(),
                "hypothesis": hyp_line.strip(),
                "reference": ref_line.strip()
            }
            json.dump(entry, out_file, ensure_ascii=False)
            out_file.write('\n')


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("srcFile")
    parser.add_argument("hypFile")
    parser.add_argument("refFile")
    parser.add_argument("outFile")

    args = parser.parse_args()
    create_jsonl(args.srcFile, args.hypFile, args.refFile, args.outFile)

