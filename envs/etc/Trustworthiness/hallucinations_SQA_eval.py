#! /usr/bin/env python

import json
import sys
import argparse
from pathlib import Path

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
parser.add_argument("hyp", type=Path, help="json file with hypotheses")
parser.add_argument("ref", type=Path, help="json file with references")
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
hypDict = json.loads(hypFile.read_text())
refList = json.loads(refFile.read_text())["data"]

model = "KRLabsOrg/lettucedect-large-modernbert-en-v1"
if baseModelFlag:
    model = "KRLabsOrg/lettucedect-base-modernbert-en-v1"


debug(f'before loading model {model}')
# For a transformer-based approach:
detector = HallucinationDetector(
    method="transformer", model_path=model
)
debug(f'after loading model {model}')

idList = list(hypDict.keys())
debug(f'{len(idList)} {len(hypDict)} {len(refList)}')

spanHal = 0
for article in refList:
    debug(f'scan paragraph {len(article["paragraphs"])}')
    for paragraph in article["paragraphs"]:
        debug(f'scan qas {len(paragraph["qas"])}')
        if len(paragraph["qas"]) == 0:
            continue
        context = paragraph["context"]
        for qa in paragraph["qas"]:
            question_id = qa["id"]
            if question_id not in idList:
                # SQuAD is a superset of Spoken-SQuAD, so some
                # questions in the dataset may not be present in the
                # predictions.
                debug(f'  missing {question_id}')
                continue
            debug(f'  processing {question_id}')
            try:
                refS = qa["question"]
                hypS = hypDict[question_id]
                predictions = detector.predict(context=context, question=refS, answer=hypS, output_format="spans")
                if len(predictions) == 0:
                    debug(f'    no-predictions {question_id}')
                    continue
                for p in predictions:
                    conf = p["confidence"]
                    if conf >= MinConfidence:
                        spanHal += 1
                        debug(f'    added hallucination {question_id} given {p}')
                        break
                    else:
                        debug(f'    skipped {question_id} {conf}')
            except Exception as e:
                debug (e)
                sys.exit(-1)
        debug(f'  done qua {spanHal}')
        

numEntries = len(idList)
metricValue = spanHal / numEntries
scores = { "hallucinated_answers_ratio" : metricValue }

print(json.dumps({ "state": "OK", "scores": scores }))


sys.exit(0)
