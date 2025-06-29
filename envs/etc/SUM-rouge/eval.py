import rouge
import json
import sys
import argparse

debugFlag = False

def debug(msg):
    if debugFlag:
        print(f'{msg}', file=sys.stderr)
    

def getHypDictFromJsonlFile(f):
    resD = {}
    debug(f'Hyp {f}')
    with open(f, "r") as fp:
        for line in fp:
            dataset = json.loads(line)
            id = dataset["id"]
            hyp = dataset["hypothesis"]
            resD[id] = hyp
    return resD


def getRefDictFromJsonlFile(f):
    resD = {}
    debug(f'Ref {f}')
    with open(f, "r") as fp:
        for line in fp:
            dataset = json.loads(line)
            id = dataset["id"]
            ref = dataset["target"]
            resD[id] = ref
    return resD


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--debug", action="store_true")
    parser.add_argument("hypFile")
    parser.add_argument("refFile")
    args = parser.parse_args()

    if args.debug:
        global debugFlag
        debugFlag = True
    hypFile = args.hypFile
    refFile = args.refFile
    hypDict = getHypDictFromJsonlFile(hypFile)
    refDict = getRefDictFromJsonlFile(refFile)
    debug(f'found {len(hypDict)} hyp from {hypFile}')
    debug(f'found {len(refDict)} ref from {refFile}')
    all_hypothesis = []
    all_references = []
    for k in dict(sorted(hypDict.items())):
        all_hypothesis.append(hypDict[k])
        all_references.append(refDict[k])
        debug(f'  adding {k}')
    debug(f'added {len(all_hypothesis)} hyp, {len(all_references)} ref')

    valid_examples = [i for i, hypo in enumerate(all_hypothesis) if hypo != ""]
    debug(f'valid_examples {len(valid_examples)}')

    aggregator = 'Avg'
    apply_avg = aggregator == 'Avg'
    apply_best = aggregator == 'Best'
    debug(f'Evaluation with {aggregator}: apply_avg {apply_avg}, apply_best {apply_best}')

    # Felix
    evaluator = rouge.Rouge(metrics=["rouge-n", "rouge-l"], max_n=2, limit_length=False, apply_avg=apply_avg, apply_best=apply_best, weight_factor=1.0, stemming=True)

    scores = evaluator.get_scores(all_hypothesis, all_references)
    debug(f'scores {scores}')

    r1Fstr = float(f'{scores["rouge-1"]["f"]*100:.1f}')
    r1Pstr = float(f'{scores["rouge-1"]["p"]*100:.1f}')
    r1Rstr = float(f'{scores["rouge-1"]["r"]*100:.1f}')
    r2Fstr = float(f'{scores["rouge-2"]["f"]*100:.1f}')
    r2Pstr = float(f'{scores["rouge-2"]["p"]*100:.1f}')
    r2Rstr = float(f'{scores["rouge-2"]["r"]*100:.1f}')
    rLFstr = float(f'{scores["rouge-l"]["f"]*100:.1f}')
    rLPstr = float(f'{scores["rouge-l"]["p"]*100:.1f}')
    rLRstr = float(f'{scores["rouge-l"]["r"]*100:.1f}')

    res = {"R-1_F1": r1Fstr, "R-1_precision": r1Pstr, "R-1_recall": r1Rstr,
           "R-2_F1": r2Fstr, "R-2_precision": r2Pstr, "R-2_recall": r2Rstr,
           "R-L_F1": rLFstr, "R-L_precision": rLPstr, "R-L_recall": rLRstr}
    print(json.dumps(res))

            
if __name__ == "__main__":
    main()
