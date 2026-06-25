#! /usr/bin/env python

import sys
import argparse
import json
import csv
import numpy as np
from sklearn.metrics import average_precision_score, precision_recall_curve, precision_score,  recall_score, f1_score


def debug(msg):
    if DebugFlag:
        print(f'{msg}', file=sys.stderr)

def loadTsvEntries(tsvFile, is_hypothesis=True):
    entryDict = {}
    try:
        with open(tsvFile, "r") as f:
            ## rd = csv.reader(f, delimiter="\t", quotechar='"')
            rd = csv.reader(f, delimiter="\t")
            for row in rd:
                videoId = row[0]
                # time_stamp_start
                tsStart = discretizeTimeStampTo25FPS(float(row[1]))
                # time_stamp_end
                tsEnd = discretizeTimeStampTo25FPS(float(row[2]))
                spkID = row[3]
                label = row[4]
                fVal = float(label)
                iVal = int(fVal)
                if is_hypothesis:
                    # could be the label 0|1 or a confidence score <= 1.0
                    if abs(fVal - iVal) < 0.001:
                        label = iVal
                    else:
                        label = fVal
                else:
                    # the label 0|1
                    label = iVal

                ## debug(f'   processing {videoId} {spkID} {tsStart} {tsEnd} {label}')
                if videoId in entryDict:
                    if spkID in entryDict[videoId]:
                        l = entryDict[videoId][spkID]
                        l.append([tsStart, tsEnd, label])
                        entryDict[videoId][spkID] = l
                    else:
                        entryDict[videoId][spkID] = [ [tsStart, tsEnd, label] ]
                else:
                    entryDict[videoId] = {}
                    entryDict[videoId][spkID] = [ [tsStart, tsEnd, label] ]
    except Exception as e:
        print(json.dumps({
            "state": "ERROR",
            "reason": str(e),
            "scores": {}
        }))
        sys.exit(0)
    return entryDict


def debugEntries(entryDict):
    for videoId,d in entryDict.items():
        debug(f'  {videoId}')
        for spkId,eList in d.items():
            debug(f'    {spkId}')
            for l in eList:
                debug(f'      {l}')


def discretizeTimeStampTo25FPS(ts):
    baseTimeMs = 40
    intPartSec = int(ts)
    fractPartMs = int((ts % 1) * 1000)
    f1 = int(fractPartMs / 40) * 40
    f2 = (int(fractPartMs / 40) + 1) * 40
    if (f2 - fractPartMs) < (fractPartMs - f1):
        return intPartSec + f2 / 1000
    else:
        return intPartSec + f1 / 1000

    
def getInfoDictFromEntries(entryDict):
    #
    # { $VIDEO : { "minTs": $MIN_TIME_STAMP,
    #              "maxTs": $MAX_TIME_STAMP,
    #              "speakers": [ $SPK1, $SPK2, .. , $SPKn ]
    #            }
    # }
    infoDict = {}
    # get min and max timestamps
    for videoId,d in entryDict.items():
        infoDict[videoId] = {}
        infoDict[videoId]["speakers"] = list(d.keys())
        minTS = 99e99
        maxTS = -1
        for spkId,eList in d.items():
            for entry in eList:
                tsStart = entry[0]
                if tsStart < minTS:
                    minTS = tsStart
                tsEnd = entry[1]
                if tsEnd > maxTS:
                    maxTS = tsEnd
        infoDict[videoId]["minTs"] = minTS
        infoDict[videoId]["maxTs"] = maxTS
    return infoDict


def getGlobalInfoDict(infoDict1, infoDict2):
    gInfoDict = {}
    #
    videoDict = {}
    # build the dict of videoIds
    for videoId in infoDict1.keys():
        videoDict[videoId] = 1
    for videoId in infoDict2.keys():
        videoDict[videoId] = 1
    #
    # for each video compute the speaker, the minTs and the maxTS
    for videoId in videoDict.keys():
        if videoId in infoDict1:
            min1 = infoDict1[videoId]["minTs"]
            max1 = infoDict1[videoId]["maxTs"]
            spkL1 = infoDict1[videoId]["speakers"]
        else:
            min1 = 99e99
            max1 = -1
            spkL1 = []
        if videoId in infoDict2:
            min2 = infoDict2[videoId]["minTs"]
            max2 = infoDict2[videoId]["maxTs"]
            spkL2 = infoDict2[videoId]["speakers"]
        else:
            min2 = 99e99
            max2 = -1
            spkL2 = []
        #
        gInfoDict[videoId] = {}
        # join the two speaker lists without duplicates
        spkLG = list(spkL1)
        spkLG.extend(x for x in spkL2 if x not in spkLG)
        gInfoDict[videoId]["speakers"] = spkLG
        if min1 < min2:
            gInfoDict[videoId]["minTs"] = min1
        else:
            gInfoDict[videoId]["minTs"] = min2
        if max1 > max2:
            gInfoDict[videoId]["maxTs"] = max1
        else:
            gInfoDict[videoId]["maxTs"] = max2
    #
    return gInfoDict


def isIntervalContained(interval, entryL):
    # interval = [ start_time, end_time ]
    # entryL = [ [ start_time, end_time, label ]+ ]
    s1 = round(interval[0] * 100)
    e1 = round(interval[1] * 100)
    for e in entryL:
        s2 = round(e[0] * 100)
        e2 = round(e[1] * 100)
        if s1 >= s2 and e1 <= e2:
            label = e[2]
            ## debug(f'  isIntervalContained YES {s1} {e1} in {s2} {e2}')
            return True, label
        else:
            ## debug(f'  isIntervalContained NO {s1} {e1} in {s2} {e2}')
            pass
    return False, None
                
    

def getContinousStreamFromEntries(entryDict, globalInfoDict):
    csList = []
    stepMs= 0.04

    for videoId,d in globalInfoDict.items():
        minTs = globalInfoDict[videoId]["minTs"]
        maxTs = globalInfoDict[videoId]["maxTs"]
        spkL  = globalInfoDict[videoId]["speakers"]
        if not videoId in entryDict:
            # add the 0 (silence) label to all the intervals
            for spkId in spkL:
                tsS = minTs
                while tsS < maxTs:
                    tsE = tsS + stepMs
                    label = 0
                    csList.append([videoId, spkId, tsS, tsE, label])
                    tsS = tsE
        else:
            for spkId in spkL:
                if not spkId in entryDict[videoId]:
                    # add the 0 (silence) label to all the intervals
                    tsS = minTs
                    while tsS < maxTs:
                        tsE = tsS + stepMs
                        label = 0
                        csList.append([videoId, spkId, tsS, tsE, label])
                        tsS = tsE
                else:
                    entryL = entryDict[videoId][spkId]
                    # add the 0 (silence) label only outside entry intervals
                    tsS = minTs
                    while tsS < maxTs:
                        tsE = tsS + stepMs
                        flag, label = isIntervalContained([tsS, tsE], entryL)
                        if not flag:
                            label = 0
                        csList.append([videoId, spkId, tsS, tsE, label])
                        tsS = tsE
    return csList


def getHardLabel(x):
    if x>=0.5:
        return 1
    else:
        return 0



DebugFlag = False

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--debug", action="store_true")
    parser.add_argument("hypTSVFile")
    parser.add_argument("refTSVFile")
    args = parser.parse_args()
    hypF  = args.hypTSVFile
    refF  = args.refTSVFile
    if args.debug:
        DebugFlag = True

    hypDict = loadTsvEntries(hypF)
    debug(f'hypDict:')
    debugEntries(hypDict)
    
    refDict = loadTsvEntries(refF, is_hypothesis=False)
    debug(f'refDict:')
    debugEntries(refDict)

    hypInfoDict = getInfoDictFromEntries(hypDict)
    refInfoDict = getInfoDictFromEntries(refDict)
    debug(f'hypInfoDict {hypInfoDict}')
    debug(f'refInfoDict {refInfoDict}')
    
    # get global info for each video
    globalInfoDict = getGlobalInfoDict(hypInfoDict, refInfoDict)
    debug(f'globalInfoDict {globalInfoDict}')

    hypCS = getContinousStreamFromEntries(hypDict, globalInfoDict)
    debug(f'hypCS {len(hypCS)}')
    ## for e in hypCS:
    ##    debug(f'  {e[0]} {e[1]} {e[2]:.2f} {e[3]:.2f} {e[4]}')

    refCS = getContinousStreamFromEntries(refDict, globalInfoDict)
    debug(f'refCS {len(refCS)}')
    ## for e in refCS:
    ##    debug(f'  {e[0]} {e[1]} {e[2]:.2f} {e[3]:.2f} {e[4]}')

    hypLabelList = [x[4] for x in hypCS]
    hypHardLabelList = [getHardLabel(x) for x in hypLabelList]
    refLabelList = [x[4] for x in refCS]
    debug(f'hypLabelList {hypLabelList}')
    debug(f'hypHardLabelList {hypHardLabelList}')
    debug(f'refLabelList {refLabelList}')
    
    y_hyp = np.array(hypLabelList)
    y_hyp_hard = np.array(hypHardLabelList)
    y_ref = np.array(refLabelList)

    # Compute the global mAP score
    map       = average_precision_score(y_ref, y_hyp)
    precision = precision_score(y_ref, y_hyp_hard)
    recall    = recall_score(y_ref, y_hyp_hard)
    f1        = f1_score(y_ref, y_hyp_hard)

    '''
    scores = {"mAP": f'{map:.4f}',
              "f1":  f'{f1:.4f}',
              "precision": f'{precision:.4f}',
              "recall": f'{recall:.4f}'}
    '''

    scores = {"mAP": map,
              "f1":  f1,
              "precision": precision,
              "recall": recall}

    print(json.dumps({
        "state": "OK",
        "scores": scores
    }))
