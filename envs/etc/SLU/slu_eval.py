#!/usr/bin/env python
# coding: utf-8


# ## SUPERB type SLU metrics (slot_type_f1, slot_value_cer)
# - Code can be found here (https://gitlab.fbk.eu/mt/speech-massive/-/blob/main/src/speech_massive/examples/scripts/s3prl_slot_eval.py)


# Copyright 2024 FBK and NAVER LABS Europe. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
original evaluation code from s3prl code repository
https://github.com/s3prl/s3prl/blob/aa3ba844bfe2b5402b7f345cbebd72b33ef6aeff/s3prl/metric/common.py
https://github.com/s3prl/s3prl/blob/aa3ba844bfe2b5402b7f345cbebd72b33ef6aeff/s3prl/metric/slot_filling.py

Original authors
Commonly used metrics

Authors
  * Shu-wen Yang 2022
  * Heng-Jui Chang 2022
  * Haibin Wu 2022

Metrics for the slot filling SLU task

Authors:
  * Yung-Sung Chuang 2021
  * Heng-Jui Chang 2022
"""


import re
from typing import Dict, List, Tuple, Union
import editdistance as ed
from scipy.interpolate import interp1d
from scipy.optimize import brentq
from sklearn.metrics import roc_curve


def accuracy(xs, ys, item_same_fn=None):
    if isinstance(xs, (tuple, list)):
        assert isinstance(ys, (tuple, list))
        return _accuracy_impl(xs, ys, item_same_fn)
    elif isinstance(xs, dict):
        assert isinstance(ys, dict)
        keys = sorted(list(xs.keys()))
        xs = [xs[k] for k in keys]
        ys = [ys[k] for k in keys]
        return _accuracy_impl(xs, ys, item_same_fn)
    else:
        raise ValueError


def _accuracy_impl(xs, ys, item_same_fn=None):
    item_same_fn = item_same_fn or (lambda x, y: x == y)
    same = [int(item_same_fn(x, y)) for x, y in zip(xs, ys)]
    return sum(same) / len(same)


def ter(hyps: List[Union[str, List[str]]], refs: List[Union[str, List[str]]]) -> float:
    """Token error rate calculator.

    Args:
        hyps (List[Union[str, List[str]]]): List of hypotheses.
        refs (List[Union[str, List[str]]]): List of references.

    Returns:
        float: Averaged token error rate overall utterances.
    """
    error_tokens = 0
    total_tokens = 0
    for h, r in zip(hyps, refs):
        error_tokens += ed.eval(h, r)
        total_tokens += len(r)
    return float(error_tokens) / float(total_tokens)


def wer(hyps: List[str], refs: List[str]) -> float:
    """Word error rate calculator.

    Args:
        hyps (List[str]): List of hypotheses.
        refs (List[str]): List of references.

    Returns:
        float: Averaged word error rate overall utterances.
    """
    hyps = [h.split(" ") for h in hyps]
    refs = [r.split(" ") for r in refs]
    return ter(hyps, refs)


def per(hyps: List[str], refs: List[str]) -> float:
    """Phoneme error rate calculator.

    Args:
        hyps (List[str]): List of hypotheses.
        refs (List[str]): List of references.

    Returns:
        float: Averaged phoneme error rate overall utterances.
    """
    return wer(hyps, refs)


def cer(hyps: List[str], refs: List[str]) -> float:
    """Character error rate calculator.

    Args:
        hyps (List[str]): List of hypotheses.
        refs (List[str]): List of references.

    Returns:
        float: Averaged character error rate overall utterances.
    """
    return ter(hyps, refs)


def compute_eer(labels: List[int], scores: List[float]):
    """Compute equal error rate.

    Args:
        scores (List[float]): List of hypotheses.
        labels (List[int]): List of references.

    Returns:
        eer (float): Equal error rate.
        treshold (float): The treshold to accept a target trial.
    """
    fpr, tpr, thresholds = roc_curve(labels, scores, pos_label=1)
    eer = brentq(lambda x: 1.0 - x - interp1d(fpr, tpr)(x), 0.0, 1.0)
    threshold = interp1d(fpr, thresholds)(eer)
    return eer, threshold


def compute_minDCF(
        labels: List[int],
        scores: List[float],
        p_target: float = 0.01,
        c_miss: int = 1,
        c_fa: int = 1):
    """Compute MinDCF.
    Computes the minimum of the detection cost function.  The comments refer to
    equations in Section 3 of the NIST 2016 Speaker Recognition Evaluation Plan.

    Args:
        scores (List[float]): List of hypotheses.
        labels (List[int]): List of references.
        p (float): The prior probability of positive class.
        c_miss (int): The cost of miss.
        c_fa (int): The cost of false alarm.

    Returns:
        min_dcf (float): The calculated min_dcf.
        min_c_det_threshold (float): The treshold to calculate min_dcf.
    """
    fpr, tpr, thresholds = roc_curve(labels, scores, pos_label=1)
    fnr = 1.0 - tpr

    min_c_det = float("inf")
    min_c_det_threshold = thresholds[0]
    for i in range(0, len(fnr)):
        c_det = c_miss * fnr[i] * p_target + c_fa * fpr[i] * (1 - p_target)
        if c_det < min_c_det:
            min_c_det = c_det
            min_c_det_threshold = thresholds[i]
    c_def = min(c_miss * p_target, c_fa * (1 - p_target))
    min_dcf = min_c_det / c_def
    return min_dcf, min_c_det_threshold


def clean(ref: str) -> str:
    ref = re.sub(r"B\-(\S+) ", "", ref)
    ref = re.sub(r" E\-(\S+)", "", ref)
    return ref


def parse(hyp: str, ref: str) -> Tuple[str, str, str, str]:
    gex = re.compile(r"B\-(\S+) (.+?) E\-\1")

    hyp = re.sub(r" +", " ", hyp)
    ref = re.sub(r" +", " ", ref)

    hyp_slots = gex.findall(hyp)
    ref_slots = gex.findall(ref)

    ref_slots = ";".join([":".join([x[1], x[0]]) for x in ref_slots])
    if len(hyp_slots) > 0:
        hyp_slots = ";".join([":".join([clean(x[1]), x[0]]) for x in hyp_slots])
    else:
        hyp_slots = ""

    ref = clean(ref)
    hyp = clean(hyp)

    return ref, hyp, ref_slots, hyp_slots


def get_slot_dict(
        pred_slot,
        pred_transcript,
        label_slot,
        label_transcript) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    hyp_dict, ref_dict = {}, {}

    for slot_tok, transcript_tok in zip(
            pred_slot.split(), pred_transcript.split()):
        hyp_dict.setdefault(slot_tok, [])
        hyp_dict[slot_tok].append(transcript_tok)

    for slot_tok, transcript_tok in zip(
            label_slot.split(), label_transcript.split()):
        ref_dict.setdefault(slot_tok, [])
        ref_dict[slot_tok].append(transcript_tok)

    return ref_dict, hyp_dict


def slot_type_f1(
        slots_pred_list,
        transcript_pred_list,
        slots_label_list,
        transcript_label_list) -> float:
    F1s = []

    for p_slot, p_trans, t_slot, t_trans in zip(
            slots_pred_list,
            transcript_pred_list,
            slots_label_list,
            transcript_label_list):
        ref_dict, hyp_dict = get_slot_dict(p_slot, p_trans, t_slot, t_trans)

        if len(hyp_dict.keys()) == 0 and len(ref_dict.keys()) == 0:
            F1 = 1.0
        elif len(hyp_dict.keys()) == 0:
            F1 = 0.0
        elif len(ref_dict.keys()) == 0:
            F1 = 0.0
        else:
            P, R = 0.0, 0.0
            for slot in ref_dict:
                if slot in hyp_dict:
                    R += 1
            R = R / len(ref_dict.keys())
            for slot in hyp_dict:
                if slot in ref_dict:
                    P += 1
            P = P / len(hyp_dict.keys())
            F1 = 2 * P * R / (P + R) if (P + R) > 0 else 0.0
        F1s.append(F1)

    return sum(F1s) / len(F1s)


def slot_value_cer(
        slots_pred_list,
        transcript_pred_list,
        slots_label_list,
        transcript_label_list) -> float:
    value_hyps, value_refs = [], []

    for p_slot, p_trans, t_slot, t_trans in zip(
            slots_pred_list,
            transcript_pred_list,
            slots_label_list,
            transcript_label_list):
        ref_dict, hyp_dict = get_slot_dict(p_slot, p_trans, t_slot, t_trans)

        # Slot Value WER/CER evaluation
        unique_slots = list(ref_dict.keys())
        for slot in unique_slots:
            for ref_i, ref_v in enumerate(ref_dict[slot]):
                if slot not in hyp_dict:
                    hyp_v = ""
                    value_refs.append(ref_v)
                    value_hyps.append(hyp_v)
                else:
                    min_cer = 100
                    best_hyp_v = ""
                    for hyp_v in hyp_dict[slot]:
                        tmp_cer = cer([hyp_v], [ref_v])
                        if min_cer > tmp_cer:
                            min_cer = tmp_cer
                            best_hyp_v = hyp_v
                    value_refs.append(ref_v)
                    value_hyps.append(best_hyp_v)

    return cer(value_hyps, value_refs)


def slot_value_wer(hypothesis: List[str], groundtruth: List[str], **kwargs) -> float:
    value_hyps = []
    value_refs = []
    for p, t in zip(hypothesis, groundtruth):
        ref_dict, hyp_dict = get_slot_dict(p, t)

        # Slot Value WER/CER evaluation
        unique_slots = list(ref_dict.keys())
        for slot in unique_slots:
            for ref_i, ref_v in enumerate(ref_dict[slot]):
                if slot not in hyp_dict:
                    hyp_v = ""
                    value_refs.append(ref_v)
                    value_hyps.append(hyp_v)
                else:
                    min_wer = 100
                    best_hyp_v = ""
                    for hyp_v in hyp_dict[slot]:
                        tmp_wer = wer([hyp_v], [ref_v])
                        if min_wer > tmp_wer:
                            min_wer = tmp_wer
                            best_hyp_v = hyp_v
                    value_refs.append(ref_v)
                    value_hyps.append(best_hyp_v)

    return wer(value_hyps, value_refs)


def slot_edit_f1(
        hypothesis: List[str],
        groundtruth: List[str],
        loop_over_all_slot: bool,
        **kwargs) -> float:
    slot2F1 = {}  # defaultdict(lambda: [0,0,0]) # TPs, FNs, FPs
    for p, t in zip(hypothesis, groundtruth):
        ref_dict, hyp_dict = get_slot_dict(p, t)

        # Collecting unique slots
        unique_slots = list(ref_dict.keys())
        if loop_over_all_slot:
            unique_slots += [x for x in hyp_dict if x not in ref_dict]
        # Evaluating slot edit F1
        for slot in unique_slots:
            TP = 0
            FP = 0
            FN = 0
            # this never happens in list(ref_dict.keys())
            if slot not in ref_dict:
                for hyp_v in hyp_dict[slot]:
                    FP += 1
            else:
                for ref_i, ref_v in enumerate(ref_dict[slot]):
                    if slot not in hyp_dict:
                        FN += 1
                    else:
                        match = False
                        for hyp_v in hyp_dict[slot]:
                            # if ref_i < len(hyp_dict[slot]):
                            #    hyp_v = hyp_dict[slot][ref_i]
                            if hyp_v == ref_v:
                                match = True
                                break
                        if match:
                            TP += 1
                        else:
                            FN += 1
                            FP += 1
            slot2F1.setdefault(slot, [0, 0, 0])
            slot2F1[slot][0] += TP
            slot2F1[slot][1] += FN
            slot2F1[slot][2] += FP

    all_TPs, all_FNs, all_FPs = 0, 0, 0
    for slot in slot2F1.keys():
        all_TPs += slot2F1[slot][0]
        all_FNs += slot2F1[slot][1]
        all_FPs += slot2F1[slot][2]

    return 2 * all_TPs / (2 * all_TPs + all_FPs + all_FNs)


def slot_edit_f1_full(hypothesis: List[str], groundtruth: List[str], **kwargs) -> float:
    return slot_edit_f1(
        hypothesis, groundtruth, loop_over_all_slot=True, **kwargs)


def slot_edit_f1_part(hypothesis: List[str], groundtruth: List[str], **kwargs) -> float:
    return slot_edit_f1(
        hypothesis, groundtruth, loop_over_all_slot=False, **kwargs)


# ## MASSIVE type SLU metrics (intent, slot_f1, exact match accuracy)
# - Code can be found here (https://gitlab.fbk.eu/mt/speech-massive/-/blob/main/src/speech_massive/examples/scripts/massive_eval.py)

# Copyright 2024 FBK and NAVER LABS Europe. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
original evaluation code from MASSIVE code repository
https://github.com/alexa/massive/blob/main/src/massive/utils/training_utils.py

"""

from math import sqrt
from seqeval.metrics import f1_score
import sklearn.metrics as sklm


class MassiveEval:

    def __init__(self):
        self.t2t_args = {
            "input_prompt": "Annotate: ",
            "use_output_descrip": False,
            "intent_first": False,
            "slots_mixed": False,
            "toks_in_output": False,
            "sentinels": False,
            "inside_format": "slot_name",
            "outside_label": "Other"}

    def convert_to_bio(self, seq_tags, outside="Other", labels_merge=None):
        """
        Converts a sequence of tags into BIO format. EX:

            ['city', 'city', 'Other', 'country', -100, 'Other']
            to
            ['B-city', 'I-city', 'O', 'B-country', 'I-country', 'O']
            where outside = 'Other' and labels_merge = [-100]

        :param seq_tags: the sequence of tags that should be converted
        :type seq_tags: list
        :param outside: The label(s) to put outside (ignore). Default: 'Other'
        :type outside: str or list
        :param labels_merge: The labels to merge leftward (i.e. for tokenized inputs)
        :type labels_merge: str or list
        :return: a BIO-tagged sequence
        :rtype: list
        """

        seq_tags = [str(x) for x in seq_tags]

        outside = [outside] if type(outside) is not list else outside
        outside = [str(x) for x in outside]

        if labels_merge:
            labels_merge = [labels_merge] if type(labels_merge) is not list else labels_merge
            labels_merge = [str(x) for x in labels_merge]
        else:
            labels_merge = []

        bio_tagged = []
        prev_tag = None
        for tag in seq_tags:
            if prev_tag is None and tag in labels_merge:
                bio_tagged.append("O")
            elif tag in outside:
                bio_tagged.append("O")
                prev_tag = tag
            elif tag != prev_tag and tag not in labels_merge:
                bio_tagged.append("B-" + tag)
                prev_tag = tag
            elif tag == prev_tag or tag in labels_merge:
                if prev_tag in outside:
                    bio_tagged.append("O")
                else:
                    bio_tagged.append("I-" + prev_tag)

        return bio_tagged

    def eval_preds(
            self,
            pred_intents=None,
            lab_intents=None,
            pred_slots=None,
            lab_slots=None,
            eval_metrics="all",
            labels_ignore="Other",
            labels_merge=None,
            pad="Other"):
        """
        Function to evaluate the predictions from a model

        :param pred_intents: a list of predicted intents
        :type pred_intents: list
        :param lab_intents: a list of intents labels (ground truth)
        :type lab_intents: list
        :param pred_slots:
        a list of predicted slots,
        where each entry is a list of token-based slots
        :type pred_slots: list
        :param lab_slots: a list of slots labels (ground truth)
        :type lab_slots: list
        :param eval_metrics: The metrics to include.
                             Options are 'all', 'intent_acc', 'ex_match_acc', 'slot_micro_f1'
        :type eval_metrics: str
        :param labels_ignore: The labels to ignore (prune away). Default: ['Other']
        :type labels_ignore: str or list
        :param labels_merge: The labels to merge leftward (i.e. for tokenized inputs)
        :type labels_merge: str or list
        :param pad: The value to use when padding slot predictions to match
                    the length of ground truth
        :type pad: str
        """

        results = {}

        # Check lengths
        if pred_intents is not None and lab_intents is not None:
            assert len(pred_intents) == len(lab_intents), \
                "pred_intents and lab_intents must be same len"
        if pred_slots is not None and lab_slots is not None:
            assert len(pred_slots) == len(lab_slots), \
                "pred_slots and lab_slots must be same length"

        if ("intent_acc" in eval_metrics) or ("all" in eval_metrics):
            intent_acc = sklm.accuracy_score(lab_intents, pred_intents)
            results["intent_acc"] = intent_acc
            # Assuming normal distribution. Multiply by z (from "z table") to get confidence int
            results["intent_acc_stderr"] = sqrt(intent_acc * (1 - intent_acc) / len(pred_intents))

        if lab_slots is not None and pred_slots is not None:
            bio_slot_labels, bio_slot_preds = [], []
            for lab, pred in zip(lab_slots, pred_slots):

                # Pad or truncate prediction as needed using `pad` arg
                if type(pred) is list:
                    pred = pred[: len(lab)] + [pad] * (len(lab) - len(pred))

                # Fix for Issue 21 -- subwords after the first one from a word should be ignored
                for i, x in enumerate(lab):
                    if x == -100:
                        pred[i] = -100

                # convert to BIO
                bio_slot_labels.append(
                    self.convert_to_bio(lab, outside=labels_ignore, labels_merge=labels_merge))
                bio_slot_preds.append(
                    self.convert_to_bio(pred, outside=labels_ignore, labels_merge=labels_merge))

        if ("slot_micro_f1" in eval_metrics) or ("all" in eval_metrics):

            # from seqeval
            ## smf1 = f1_score(bio_slot_labels, bio_slot_preds)
            smf1 = float(f1_score(bio_slot_labels, bio_slot_preds))
            results["slot_micro_f1"] = smf1
            # Assuming normal distribution. Multiply by z (from "z table") to get confidence int
            total_slots = sum([len(x) for x in bio_slot_preds])
            results["slot_micro_f1_stderr"] = sqrt(smf1 * (1 - smf1) / total_slots)

        if ("ex_match_acc" in eval_metrics) or ("all" in eval_metrics):
            # calculate exact match accuracy (~0.01 seconds)
            matches = 0
            denom = 0
            for p_int, p_slot, l_int, l_slot in zip(
                    pred_intents, bio_slot_preds, lab_intents, bio_slot_labels):

                if (p_int == l_int) and (p_slot == l_slot):
                    matches += 1
                denom += 1
            emacc = matches / denom

            results["ex_match_acc"] = emacc
            # Assuming normal distribution. Multiply by z (from "z table") to get confidence int
            results["ex_match_acc_stderr"] = sqrt(emacc * (1 - emacc) / len(pred_intents))

        return results

    def convert_t2t_batch_to_intents_slots(
            self,
            mod_out,
            use_output_descrip=False,
            intent_first=False,
            slots_mixed=False,
            toks_in_output=False,
            sentinels=False,
            inside_format="slot_name",
            outside_label="Other",
            **kwargs):
        """
        Helper function to convert an intent and 0 or more slots to a text-to-text format

        :param model_out: A list of outputs from the model, each a detokenized string
        :type model_out: list
        :param use_output_descrip:
            Whether or not to include descriptive prompts in the output,
            being 'tokens: ' and 'annotations' for non mixed slotting or 'annotation: '
            for mixed slotting. Default: False
        :type use_output_descrip: bool
        :param intent_first:
            Whether to put the intent before the slots and utterance (True) or
            after Default: True
        :type intent_first: bool
        :param slots_mixed:
            Whether to put each slot after its respective token (True) or
            to put all slots after all tokens (False). Default: False
        :type slots_mixed: bool
        :param input_prompt:
            The text prompt for the input. Leave blank for no prompt.
            Default: 'Annotate: '
        :type input_prompt: str
        :param toks_in_output:
            Whether to put tokens in the output or not. Default: False.
            If this is True, then slots_mixed must be False
        :type toks_in_output: bool
        :param sentinels:
            Whether to add T5 sentinels before each token. Overrides toks_in_output and
            slots_mixed. Default: False
            See: https://arxiv.org/pdf/2203.08378.pdf
        :type sentinels: bool
        :param inside_format:
            The slot to use for the inside of a multi-word slot. Options are
            "slot_name", in which the slot name is repeated, "inside_slot_name",
            in which "I-" is added to the slot name, or "inside", in which "I" is
            used on its own.
        :type inside_format: str
        :param outside_label: The word used for non-slotted tokens. Default: Other
        :type outside_label: str

        :return: a list of intents, a list of slot lists
        :rtype: list
        """

        if sentinels:
            # using sentinels is the same as doing slots_mixed and toks_in_output and
            # converting the utterance to a sequence of sentinels
            toks_in_output = True
            slots_mixed = True
            for example in mod_out:
                new_utt, sent_id = [], 0
                for tok in example:
                    new_utt.append("<extra_id_" + str(sent_id) + ">")
                    sent_id += 1
                example = new_utt

        # Get intents
        if intent_first and use_output_descrip:
            # Note: this assumes that the description is one word
            intents_pred = [x.split()[1] if len(x.split()) > 1 else "" for x in mod_out]
        elif intent_first:
            intents_pred = [x.split()[0] for x in mod_out]
        else:
            intents_pred = []
            for x in mod_out:
                try:
                    intents_pred.append(x.split()[-1])
                except IndexError:
                    intents_pred.append("")
            # intents_pred = [x.split()[-1] for x in mod_out]

        # Determine Slots. Note: this assumes that the description is one word
        descrip_shift = 0
        if use_output_descrip:
            descrip_shift = 1

        if intent_first:
            # Everthing after the intent
            slot_chunk_pred = [x.split()[(1 + 2 * descrip_shift):] for x in mod_out]
        else:
            # Everything until the intent
            slot_chunk_pred = [
                x.split()[(descrip_shift): (-1 * (descrip_shift + 1))]
                for x in mod_out]
        if toks_in_output and slots_mixed:
            # Grab every other item
            slots_pred = [x[1::2] for x in slot_chunk_pred]
        elif toks_in_output:
            slots_pred = []
            # Assume equal number of tokens and slots and take second half
            for pred in slot_chunk_pred:
                pred = pred[descrip_shift:]
                mid = len(pred) // 2
                slots_pred.append(pred[mid:])
        else:
            slots_pred = slot_chunk_pred

        # Modify for inside format if needed
        for s_idx, slots in enumerate(slots_pred):
            new_slots = []
            for idx, slot in enumerate(slots):
                if idx > 0 and slot != outside_label:
                    if inside_format == "inside_slot_name":
                        if slot.startswith("I-"):
                            new_slots.append(slots[idx - 1])
                            continue
                    elif inside_format == "inside":
                        if slot == "I":
                            new_slots.append(slots[idx - 1])
                            continue
                new_slots.append(slot)
            slots_pred[s_idx] = new_slots

        return intents_pred, slots_pred

# end of class MassiveEval


def _parse_prediction(target_format_content, separator, pred_list):
    output = {
        "massive_nlu_eval_format": [],
        "transcript": [],
        "slots": [],
        "intent": []}

    for pred in pred_list:
        if target_format_content == "transcript_slots_intent":
            splitted = pred.split(separator)
            transcript_pred = ""
            slots_pred = ""
            intent_pred = ""

            if len(splitted) >= 3:
                transcript_pred = splitted[0].strip()
                slots_pred = splitted[1].strip()
                intent_pred = splitted[2].strip()
            elif len(splitted) == 2:
                transcript_pred = splitted[0].strip()
                slots_pred = splitted[1].strip()
            elif len(splitted) == 1:
                transcript_pred = splitted[0].strip()
            else:
                pass
            massive_nlu_eval_format = f"{slots_pred} {intent_pred}"
            if not slots_pred and not intent_pred:
                massive_nlu_eval_format = ""
        else:
            print('unsupported format')

        output["massive_nlu_eval_format"].append(massive_nlu_eval_format)
        output["transcript"].append(transcript_pred),
        output["slots"].append(slots_pred),
        output["intent"].append(intent_pred)

    return output


import argparse
import json

debugFlag = False

def debug(msg):
    if debugFlag:
        print(f'{msg}', file=sys.stderr)
    

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

    language = 'es_ES'
    pred_file_reads  = open(hypFile, 'r').readlines()
    label_file_reads = open(refFile, 'r').readlines()

    pred_parse_result_list = _parse_prediction(
        'transcript_slots_intent',
        '|',
        pred_file_reads)
    label_parse_result_list = _parse_prediction(
        'transcript_slots_intent',
        '|',
        label_file_reads)

    massive_nlu_eval_format_pred = pred_parse_result_list["massive_nlu_eval_format"]
    transcript_pred_list = pred_parse_result_list["transcript"]
    slots_pred_list = pred_parse_result_list["slots"]

    massive_nlu_eval_format_label = label_parse_result_list["massive_nlu_eval_format"]
    transcript_label_list = label_parse_result_list["transcript"]
    slots_label_list = label_parse_result_list["slots"]

    superb_type_slot_type_f1_value = slot_type_f1(
        slots_pred_list,
        transcript_pred_list,
        slots_label_list,
        transcript_label_list)

    superb_type_slot_value_cer_value = slot_value_cer(
        slots_pred_list,
        transcript_pred_list,
        slots_label_list,
        transcript_label_list)

    eval_result = {}
    eval_result["slot_type_f1"] = superb_type_slot_type_f1_value
    eval_result["slot_value_cer"] = superb_type_slot_value_cer_value

    massive_type_eval_instance = MassiveEval()
    intents_pred, slots_pred_all = massive_type_eval_instance.convert_t2t_batch_to_intents_slots(massive_nlu_eval_format_pred, massive_type_eval_instance.t2t_args)
    intents_lab, slots_lab_all = massive_type_eval_instance.convert_t2t_batch_to_intents_slots(massive_nlu_eval_format_label, massive_type_eval_instance.t2t_args)

    ia_result = massive_type_eval_instance.eval_preds(
        pred_intents=intents_pred,
        lab_intents=intents_lab,
        pred_slots=slots_pred_all,
        lab_slots=slots_lab_all,
        eval_metrics="intent_acc",
        labels_ignore="Other",
        pad="Other")

    eval_result["intent_accuracy_mean"] = ia_result["intent_acc"]
    eval_result["intent_accuracy_standard_error"] = ia_result["intent_acc_stderr"]


    print(json.dumps(eval_result))

            
if __name__ == "__main__":
    main()
