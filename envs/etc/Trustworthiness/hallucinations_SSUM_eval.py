#! /usr/bin/env python

import json
import sys
import argparse

from lettucedetect.models.inference import HallucinationDetector

MinConfidence = 0.9

debugFlag = False
baseModelFlag = False

def debug(msg):
    global debugFlag
    if debugFlag:
        print(f'{msg}', file=sys.stderr)


parser = argparse.ArgumentParser()
parser.add_argument("-b", "--base-model", action="store_true")
parser.add_argument("-d", "--debug", action="store_true")
parser.add_argument("hyp", help="jsonl file with hypotheses")
parser.add_argument("ref", help="jsonl file with references")
args = parser.parse_args()
hypFile = args.hyp
refFile = args.ref
if args.base_model:
    baseModelFlag = args.base_model
if args.debug:
    debugFlag = args.debug
debug(f'args: {debugFlag} {baseModelFlag} {hypFile} {refFile}')
#
idList = []
hypDict = {}
refDict = {}
#
with open(hypFile) as file:
    for line in file:
        entry = json.loads(line)
        id = entry["id"]
        hypDict[id] = entry
        idList.append(id)
#
with open(refFile) as file:
    for line in file:
        entry = json.loads(line)
        id = entry["id"]
        refDict[id] = entry

debug(f'{len(hypDict)} {len(refDict)}')

model = "KRLabsOrg/lettucedect-large-modernbert-en-v1"
if baseModelFlag:
    model = "KRLabsOrg/lettucedect-base-modernbert-en-v1"

debug(f'before loading model {model}')
# For a transformer-based approach:
detector = HallucinationDetector(
    method="transformer", model_path=model
)
debug(f'after loading model {model}')


spanHal = 0
for id in idList:
    debug(f'start {id} {spanHal}')
    try:
        hypS = hypDict[id]["hypothesis"]
        refS = refDict[id]["target"]
        context = ""
        ## debug(f'{id}\nhypS: {hypS}\nrefS: {refS}')
        predictions = detector.predict(context=context, question=refS, answer=hypS, output_format="spans")
        for p in predictions:
            conf = p["confidence"]
            if conf >= MinConfidence:
                spanHal += 1
                debug(f'  added {spanHal} given {conf}')
            else:
                debug(f'  skipped {conf}')
        ## debug(f'Predictions: {predictions}\n')
    except Exception as e:
        msg = str(e)
        print(json.dumps({ "state": "ERROR", "reason": msg }))
        sys.exit(-1)
    debug(f'end {id} {spanHal}')

numEntries = len(idList)
metricValue = spanHal / numEntries

scores = { "average_hallucinations" : metricValue }
print(json.dumps({ "state": "OK", "scores": scores }))


