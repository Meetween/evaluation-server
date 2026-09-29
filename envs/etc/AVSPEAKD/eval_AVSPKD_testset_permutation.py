#! /usr/bin/env python
#
# Variant of eval_AVSPKD_testset.py which assumes that the speaker_ids of the
# hypothesis do NOT correspond to those of the reference, but are a permutation
# of them.
#
# For each video the speaker_ids of the hypothesis are permuted, the score
# against the reference is computed, and the permutation giving the best score
# is kept.  The final scores are then computed on the whole test set with the
# best permutation applied to every video.
#
# NOTE on the search strategy
# ---------------------------
# The speaker_ids are local to each video (speaker_1..speaker_N inside a video),
# so the permutations are searched independently video by video.  Some videos of
# the VOXMM test set have many speakers (up to 73), and 73! permutations cannot
# be enumerated.  Two methods are therefore available:
#
#   * "exhaustive": enumerates all the S! permutations of a video (only usable
#     when S is small; guarded by --max-perms).
#
#   * "hungarian": solves the speaker-to-speaker assignment problem in O(S^3),
#     maximising the number of frames where hypothesis and reference are both
#     "speaking" (the TP count).
#
# The "hungarian" method is NOT a heuristic for precision/recall/f1: a
# permutation of the hypothesis speaker_ids inside a video changes neither the
# total number of predicted positive frames nor the total number of reference
# positive frames, it only changes how many of them are aligned (TP).  Hence
# maximising TP maximises precision, recall and f1 at the same time; and since
# TP is additive over the videos and over the speaker pairs, maximising it video
# by video yields the GLOBAL optimum.  For mAP (a ranking metric over the pooled
# scores) the same procedure is only a very good proxy, not a proof of optimality.
#
# The default is --criterion tp --method auto, i.e. the provably optimal choice
# for f1/precision/recall.
#

import sys
import os
import argparse
import json
import csv
import math
import itertools
import time
import numpy as np
from sklearn.metrics import average_precision_score, precision_score, recall_score, f1_score

try:
    from scipy.optimize import linear_sum_assignment as _scipy_lsa
except Exception:
    _scipy_lsa = None


def debug(msg):
    if DebugFlag:
        print(f'{msg}', file=sys.stderr)


def fail(reason):
    print(json.dumps({
        "state": "ERROR",
        "reason": str(reason),
        "scores": {}
    }))
    sys.exit(0)


# ---------------------------------------------------------------------------
# loading  (identical to eval_AVSPKD_testset.py)
# ---------------------------------------------------------------------------

def loadTsvEntries(tsvFile, is_hypothesis=True):
    entryDict = {}
    try:
        with open(tsvFile, "r") as f:
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
        fail(e)
    return entryDict


def discretizeTimeStampTo25FPS(ts):
    intPartSec = int(ts)
    fractPartMs = int((ts % 1) * 1000)
    f1 = int(fractPartMs / 40) * 40
    f2 = (int(fractPartMs / 40) + 1) * 40
    if (f2 - fractPartMs) < (fractPartMs - f1):
        return intPartSec + f2 / 1000
    else:
        return intPartSec + f1 / 1000


def getInfoDictFromEntries(entryDict):
    infoDict = {}
    for videoId, d in entryDict.items():
        infoDict[videoId] = {}
        infoDict[videoId]["speakers"] = list(d.keys())
        minTS = 99e99
        maxTS = -1
        for spkId, eList in d.items():
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
    videoDict = {}
    for videoId in infoDict1.keys():
        videoDict[videoId] = 1
    for videoId in infoDict2.keys():
        videoDict[videoId] = 1

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

        gInfoDict[videoId] = {}
        # join the two speaker lists without duplicates
        spkLG = list(spkL1)
        spkLG.extend(x for x in spkL2 if x not in spkLG)
        gInfoDict[videoId]["speakers"] = spkLG
        gInfoDict[videoId]["minTs"] = min1 if min1 < min2 else min2
        gInfoDict[videoId]["maxTs"] = max1 if max1 > max2 else max2
    return gInfoDict


# ---------------------------------------------------------------------------
# continuous frame streams, as numpy matrices (one per video)
#
# Same 40ms frames and same "first containing entry wins, else 0" labelling as
# getContinousStreamFromEntries()/isIntervalContained() of the original script,
# just vectorised and kept grouped by video so that the speaker rows can be
# permuted.
# ---------------------------------------------------------------------------

STEP_MS = 0.04


def buildFrameGrid(minTs, maxTs):
    # replicate the float accumulation of the original while-loop
    starts = []
    ends = []
    tsS = minTs
    while tsS < maxTs:
        tsE = tsS + STEP_MS
        starts.append(tsS)
        ends.append(tsE)
        tsS = tsE
    s1 = np.array([round(x * 100) for x in starts], dtype=np.int64)
    e1 = np.array([round(x * 100) for x in ends], dtype=np.int64)
    return s1, e1


def labelsForSpeaker(entryL, s1, e1):
    # entryL = [ [start_time, end_time, label]+ ]  (may be None/empty)
    #
    # s1/e1 are the (strictly increasing) centisecond bounds of the 40ms frame
    # grid, so the frames contained in an entry form a contiguous range and can
    # be located with searchsorted.  Entries are scanned in file order and only
    # the frames not yet labelled are written, which reproduces the
    # "first containing entry wins, else 0" behaviour of isIntervalContained().
    n = s1.shape[0]
    lab = np.zeros(n, dtype=np.float64)
    if not entryL:
        return lab
    assigned = np.zeros(n, dtype=bool)
    for e in entryL:
        s2 = round(e[0] * 100)
        e2 = round(e[1] * 100)
        lo = int(np.searchsorted(s1, s2, side="left"))    # first frame with s1 >= s2
        hi = int(np.searchsorted(e1, e2, side="right"))   # first frame with e1 >  e2
        if hi <= lo:
            continue
        sub = assigned[lo:hi]
        free = ~sub
        if free.any():
            lab[lo:hi][free] = e[2]
            sub |= True
    return lab


def buildVideoMatrices(entryDict, videoId, spkL, s1, e1):
    d = entryDict.get(videoId, {})
    rows = [labelsForSpeaker(d.get(spkId), s1, e1) for spkId in spkL]
    return np.stack(rows) if rows else np.zeros((0, s1.shape[0]))


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------

def getHardLabel(x):
    if x >= 0.5:
        return 1
    else:
        return 0


def hardLabels(mat):
    return (mat >= 0.5).astype(np.int64)


def computeScores(y_ref, y_hyp):
    y_hyp_hard = (y_hyp >= 0.5).astype(np.int64)
    if y_ref.sum() > 0 and len(np.unique(y_ref)) > 1:
        map_ = float(average_precision_score(y_ref, y_hyp))
    else:
        map_ = float('nan')
    return {
        "mAP":       map_,
        "f1":        float(f1_score(y_ref, y_hyp_hard, zero_division=0)),
        "precision": float(precision_score(y_ref, y_hyp_hard, zero_division=0)),
        "recall":    float(recall_score(y_ref, y_hyp_hard, zero_division=0)),
    }


def criterionValue(criterion, Rmat, Hmat):
    # Rmat, Hmat : (S, n) matrices of one video, rows already aligned
    if criterion == "tp":
        return float(np.sum(hardLabels(Hmat) * Rmat.astype(np.int64)))
    y_ref = Rmat.reshape(-1).astype(np.int64)
    y_hyp = Hmat.reshape(-1)
    sc = computeScores(y_ref, y_hyp)
    v = sc[criterion]
    if math.isnan(v):
        return float('-inf')
    return v


# ---------------------------------------------------------------------------
# assignment solver (Hungarian / Jonker-Volgenant, O(S^3)), used when the
# number of permutations is too large to be enumerated
# ---------------------------------------------------------------------------

def maximizeAssignment(profit):
    # profit : (S, S) matrix; returns col[i] = column assigned to row i
    profit = np.asarray(profit, dtype=np.float64)
    n = profit.shape[0]
    if n == 0:
        return []
    if _scipy_lsa is not None:
        r, c = _scipy_lsa(-profit)
        col = [0] * n
        for i, j in zip(r, c):
            col[i] = int(j)
        return col
    # pure-python fallback (e-maxx JV implementation, minimisation)
    a = -profit
    INF = float('inf')
    u = [0.0] * (n + 1)
    v = [0.0] * (n + 1)
    p = [0] * (n + 1)
    way = [0] * (n + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [INF] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = INF
            j1 = -1
            row = a[i0 - 1]
            ui = u[i0]
            for j in range(1, n + 1):
                if not used[j]:
                    cur = row[j - 1] - ui - v[j]
                    if cur < minv[j]:
                        minv[j] = cur
                        way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]
                        j1 = j
            for j in range(0, n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
    col = [0] * n
    for j in range(1, n + 1):
        if p[j] > 0:
            col[p[j] - 1] = j - 1
    return col


# ---------------------------------------------------------------------------
# permutation search, video by video
#
# The criteria "tp", "f1", "precision" and "recall" are monotone in TP: inside a
# video a permutation changes neither the number of predicted positive frames
# (PP) nor the number of reference positive frames (AP), so
#       precision = TP/PP     recall = TP/AP     f1 = 2TP/(PP+AP)
# are all strictly increasing functions of TP.  For those criteria the score of
# a permutation therefore depends on the frames only through the overlap matrix
#       C[i][j] = number of frames where hyp speaker i and ref speaker j both speak
# and the search becomes  max_perm  sum_j C[perm[j]][j] , i.e. a linear
# assignment problem.  C is computed once per video with a single matrix
# product, after which a permutation is scored in O(S) instead of O(S*n).
#
# "mAP" is a ranking metric over the pooled scores and is not expressible
# through C, so for that criterion the exhaustive search still rescores the
# frames and stays limited by --max-perms.
# ---------------------------------------------------------------------------

TP_MONOTONE = ("tp", "f1", "precision", "recall")


def nPermutations(s, cap):
    # factorial, saturating at cap (avoids computing 73!)
    r = 1
    for k in range(2, s + 1):
        r *= k
        if r > cap:
            return None
    return r


def overlapMatrix(Hmat, Rmat, soft=False):
    # C[i][j] = overlap between hypothesis speaker i and reference speaker j
    if soft:
        return Hmat.astype(np.float64) @ Rmat.astype(np.float64).T
    # integer frame counts -> exact arithmetic, no floating point ties
    return hardLabels(Hmat) @ Rmat.astype(np.int64).T


def greedyAssignment(C):
    # independent starting incumbent: repeatedly take the largest free entry
    S = C.shape[0]
    flat = np.argsort(C, axis=None)[::-1]
    usedR = np.zeros(S, dtype=bool)
    usedC = np.zeros(S, dtype=bool)
    perm = [-1] * S
    val = 0
    left = S
    for f in flat:
        i, j = int(f // S), int(f % S)
        if usedR[i] or usedC[j]:
            continue
        usedR[i] = True
        usedC[j] = True
        perm[j] = i
        val += int(C[i, j])
        left -= 1
        if left == 0:
            break
    if left:
        # only possible if argsort missed nothing; fill defensively
        freeR = [i for i in range(S) if not usedR[i]]
        for j in range(S):
            if perm[j] < 0:
                perm[j] = freeR.pop()
    return perm, int(val)


class _NodeLimit(Exception):
    pass


def branchAndBound(C, nodeLimit):
    """Exact maximisation of sum_j C[perm[j]][j] over all the permutations.

    The reference speakers (columns) are visited by decreasing column maximum,
    and a partial assignment is abandoned as soon as

        partial + sum of the column maxima still to be assigned  <=  incumbent

    which is a valid optimistic bound because the maximum over the still free
    rows is never larger than the maximum over all the rows.  The rows of a
    column are tried by decreasing value, so the loop can break (not continue)
    at the first row that cannot beat the incumbent.

    Returns (perm, value, nodes, upperBound, complete) where complete is False
    if the node limit was hit before the search finished.
    """
    S = C.shape[0]
    colmax = C.max(axis=0)
    order = [int(j) for j in np.argsort(-colmax)]
    # suffix sums of the column maxima -> O(1) optimistic bound at every depth
    suf = [0] * (S + 1)
    for d in range(S - 1, -1, -1):
        suf[d] = suf[d + 1] + int(colmax[order[d]])
    upperBound = suf[0]
    # rows of each column, by decreasing overlap
    colOrder = {j: [int(i) for i in np.argsort(-C[:, j])] for j in order}
    colVal = {j: [int(x) for x in C[:, j]] for j in order}

    greedyPerm, greedyVal = greedyAssignment(C)
    if greedyVal >= upperBound:
        # the whole search space is excluded by the bound alone
        return greedyPerm, greedyVal, 0, upperBound, True

    bestPerm = [greedyPerm]
    bestVal = [greedyVal]
    used = [False] * S
    cur = [0] * S
    nodes = [0]

    def dfs(d, partial):
        nodes[0] += 1
        if nodeLimit and nodes[0] > nodeLimit:
            raise _NodeLimit()
        if d == S:
            if partial > bestVal[0]:
                bestVal[0] = partial
                bestPerm[0] = list(cur)
            return
        j = order[d]
        vals = colVal[j]
        rest = suf[d + 1]
        for i in colOrder[j]:
            if used[i]:
                continue
            v = vals[i]
            if partial + v + rest <= bestVal[0]:
                break          # sorted by decreasing v: no later row can help
            used[i] = True
            cur[j] = i
            dfs(d + 1, partial + v)
            used[i] = False

    complete = True
    try:
        dfs(0, 0)
    except _NodeLimit:
        complete = False
    return bestPerm[0], bestVal[0], nodes[0], upperBound, complete


def searchBestPermutation(videoId, spkL, Hmat, Rmat, criterion, method,
                          maxPerms, bbMaxNodes):
    # returns (perm, stats) where perm[k] is the index (in spkL) of the
    # hypothesis speaker assigned to the reference speaker spkL[k]
    S = len(spkL)
    if S <= 1:
        return list(range(S)), {"method": "trivial", "evaluated": 1}

    monotone = criterion in TP_MONOTONE

    useMethod = method
    if method == "auto":
        if monotone:
            useMethod = "hungarian"          # exact and O(S^3)
        else:
            useMethod = "exhaustive" if nPermutations(S, maxPerms) is not None \
                        else "hungarian"

    # ---- naive enumeration, kept for validation --------------------------
    if useMethod == "bruteforce" or (useMethod == "exhaustive" and not monotone):
        nP = nPermutations(S, maxPerms)
        if nP is None:
            fail(f'video {videoId} has {S} speakers: {S}! permutations exceed '
                 f'--max-perms ({maxPerms}); use --method hungarian, or a criterion '
                 f'among {TP_MONOTONE} for which --method exhaustive is not limited')
        best = None
        bestPerm = None
        cnt = 0
        for perm in itertools.permutations(range(S)):
            val = criterionValue(criterion, Rmat, Hmat[list(perm), :])
            cnt += 1
            if best is None or val > best:
                best = val
                bestPerm = list(perm)
        debug(f'  {videoId}: {useMethod} over {cnt} permutations, best {criterion}={best}')
        return bestPerm, {"method": useMethod, "evaluated": cnt, "best_value": best}

    # ---- branch and bound on the overlap matrix --------------------------
    if useMethod == "exhaustive":
        C = overlapMatrix(Hmat, Rmat)
        perm, val, nodes, ub, complete = branchAndBound(C, bbMaxNodes)
        if not complete:
            debug(f'  {videoId}: branch-and-bound hit the {bbMaxNodes} node limit, '
                  f'falling back to hungarian')
            col = maximizeAssignment(C.astype(np.float64))
            permH = [0] * S
            for i, j in enumerate(col):
                permH[j] = i
            valH = int(sum(C[i][j] for i, j in enumerate(col)))
            if valH >= val:
                perm, val = permH, valH
            return perm, {"method": "exhaustive-bb-truncated", "nodes": nodes,
                          "upper_bound": int(ub), "tp": val, "exact": False}
        debug(f'  {videoId}: branch-and-bound {nodes} nodes, tp={val}, bound={ub}, '
              f'tight={val == ub}')
        return perm, {"method": "exhaustive-bb", "nodes": nodes,
                      "upper_bound": int(ub), "tp": int(val),
                      "bound_tight": bool(val == ub), "exact": True}

    # ---- hungarian -------------------------------------------------------
    C = overlapMatrix(Hmat, Rmat, soft=(criterion == "mAP"))
    col = maximizeAssignment(C.astype(np.float64))
    perm = [0] * S
    for i, j in enumerate(col):
        perm[j] = i
    val = sum(C[i][j] for i, j in enumerate(col))
    ub = float(C.max(axis=0).sum())
    debug(f'  {videoId}: hungarian over {S} speakers, value={val}, bound={ub}')
    stats = {"method": "hungarian", "evaluated": S * S * S,
             "upper_bound": float(ub), "bound_tight": bool(abs(val - ub) < 1e-9),
             "exact": bool(monotone)}
    if monotone:
        stats["tp"] = int(val)
    return perm, stats


# ---------------------------------------------------------------------------
# permuted hypothesis dump
# ---------------------------------------------------------------------------

def writePermutedHyp(hypF, outF, mapping):
    try:
        with open(hypF, "r") as fin, open(outF, "w") as fout:
            rd = csv.reader(fin, delimiter="\t")
            wr = csv.writer(fout, delimiter="\t", lineterminator="\n")
            for row in rd:
                if len(row) >= 4:
                    m = mapping.get(row[0], {})
                    row[3] = m.get(row[3], row[3])
                wr.writerow(row)
    except Exception as e:
        fail(e)


DebugFlag = False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Evaluate AVSPEAKD hypotheses whose speaker_ids are a permutation "
                    "of the reference ones: search, per video, the permutation giving "
                    "the best score.")
    parser.add_argument("-d", "--debug", action="store_true")
    parser.add_argument("-c", "--criterion", default="tp",
                        choices=["tp", "f1", "precision", "recall", "mAP"],
                        help="score maximised while searching the permutation "
                             "(default: tp, i.e. the number of correctly aligned "
                             "speaking frames; maximising it is equivalent to "
                             "maximising the global f1/precision/recall)")
    parser.add_argument("-m", "--method", default="auto",
                        choices=["auto", "exhaustive", "hungarian", "bruteforce"],
                        help="auto (default): the exact O(S^3) assignment for the "
                             "criteria monotone in tp, otherwise enumerate when the "
                             "permutations are few enough; exhaustive: branch and "
                             "bound on the overlap matrix (exact, usable for any "
                             "number of speakers) for those criteria, plain "
                             "enumeration for mAP; hungarian: always solve the "
                             "assignment problem; bruteforce: always enumerate every "
                             "permutation rescoring the frames (validation only)")
    parser.add_argument("--max-perms", type=int, default=100000,
                        help="max number of permutations enumerated per video by the "
                             "plain enumeration (default: 100000, i.e. up to 8 "
                             "speakers); does not limit the branch and bound")
    parser.add_argument("--bb-max-nodes", type=int, default=2000000,
                        help="max number of nodes explored by the branch and bound "
                             "per video (default: 2000000); on overflow the video "
                             "falls back to the assignment solution and is reported "
                             "with exact=false")
    parser.add_argument("--hyp-out", default=None,
                        help="write the hypothesis TSV with the best permutation "
                             "applied to the speaker_ids")
    parser.add_argument("--mapping-out", default=None,
                        help="write the best hyp->ref speaker_id mapping as JSON")
    parser.add_argument("hypTSVFile")
    parser.add_argument("refTSVFile")
    args = parser.parse_args()
    hypF = args.hypTSVFile
    refF = args.refTSVFile
    if args.debug:
        DebugFlag = True

    tStart = time.time()
    hypDict = loadTsvEntries(hypF)
    refDict = loadTsvEntries(refF, is_hypothesis=False)
    tLoad = time.time() - tStart

    hypInfoDict = getInfoDictFromEntries(hypDict)
    refInfoDict = getInfoDictFromEntries(refDict)
    globalInfoDict = getGlobalInfoDict(hypInfoDict, refInfoDict)
    debug(f'globalInfoDict {globalInfoDict}')

    baseHyp = []
    bestHyp = []
    allRef  = []
    mapping = {}
    perVideo = {}
    totEvaluated = 0
    tFrames = 0.0
    tSearch = 0.0

    for videoId, info in globalInfoDict.items():
        spkL = info["speakers"]
        t0 = time.time()
        s1, e1 = buildFrameGrid(info["minTs"], info["maxTs"])
        Hmat = buildVideoMatrices(hypDict, videoId, spkL, s1, e1)
        Rmat = buildVideoMatrices(refDict, videoId, spkL, s1, e1)
        tFrames += time.time() - t0
        debug(f'{videoId}: {len(spkL)} speakers, {s1.shape[0]} frames')

        t0 = time.time()
        perm, stats = searchBestPermutation(
            videoId, spkL, Hmat, Rmat, args.criterion, args.method,
            args.max_perms, args.bb_max_nodes)
        dt = time.time() - t0
        tSearch += dt
        stats["seconds"] = round(dt, 6)
        totEvaluated += stats.get("evaluated", stats.get("nodes", 0))

        Hperm = Hmat[perm, :]
        baseHyp.append(Hmat.reshape(-1))
        bestHyp.append(Hperm.reshape(-1))
        allRef.append(Rmat.reshape(-1))

        # perm[k] = index of the hypothesis speaker aligned to reference speaker spkL[k]
        m = {}
        for k, i in enumerate(perm):
            if spkL[i] in hypDict.get(videoId, {}):
                m[spkL[i]] = spkL[k]
        mapping[videoId] = m
        perVideo[videoId] = {
            "speakers": len(spkL),
            "frames": int(s1.shape[0]),
            "identity": (perm == list(range(len(spkL)))),
            "search": stats,
            "mapping": m,
        }
        debug(f'  mapping {m}')

    if not allRef:
        fail("no video found")

    y_ref  = np.concatenate(allRef).astype(np.int64)
    y_base = np.concatenate(baseHyp)
    y_best = np.concatenate(bestHyp)

    t0 = time.time()
    baselineScores = computeScores(y_ref, y_base)
    bestScores     = computeScores(y_ref, y_best)
    tScore = time.time() - t0

    if args.hyp_out:
        writePermutedHyp(hypF, args.hyp_out, mapping)
    if args.mapping_out:
        try:
            with open(args.mapping_out, "w") as f:
                json.dump(mapping, f, indent=2, sort_keys=True)
        except Exception as e:
            fail(e)

    out = {
        "state": "OK",
        "scores": bestScores,
        "baseline_scores": baselineScores,
        "timing_seconds": {
            "load": round(tLoad, 3),
            "frames": round(tFrames, 3),
            "search": round(tSearch, 6),
            "final_scoring": round(tScore, 3),
            "total": round(time.time() - tStart, 3),
        },
        "permutation": {
            "criterion": args.criterion,
            "method": args.method,
            "videos": len(globalInfoDict),
            "permutations_evaluated": totEvaluated,
            "per_video": perVideo,
        },
    }
    print(json.dumps(out))
