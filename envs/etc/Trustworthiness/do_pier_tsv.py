from jiwer import wer, cer
import jiwer
import re
import sys
from measures import pier
import argparse
import regex
import inflect
import os
import json, csv


def loadTsvEntries(tsvFile):
    entryDict = {}
    try:
        with open(tsvFile, "r") as f:
            ## rd = csv.reader(f, delimiter="\t", quotechar='"')
            rd = csv.reader(f, delimiter="\t")
            for row in rd:
                id = row[0]
                sentence = row[1]
                entryDict[id] = sentence
    except Exception as e:
        print(json.dumps({
            "state": "ERROR",
            "reason": str(e)
        }))
        sys.exit(0)
    return dict(sorted(entryDict.items()))


def normalize_text(utterance, language):
    arabic_filter = re.compile(r'[OUM]+/*|\u061F|\?|\!|\.')
    english_filter = re.compile(r'\(|\)|\#|\+|\=|\?|\!|\;|\,|\"|\:|\.')#|\.
    cyrillic_filter = re.compile(r'\(|\)|\#|\+|\=|\?|\!|\;|\,|\"|\:|\.')
    japanese_filter = re.compile(r'\(|\)|\#|\+|\=|\?|\!|\;|\,|\"|\:|\.|\u3002|\u300C|\u300D|\uFF08|\uFF09|\uFF0C|\uFF1F|\uFF01|\uFF1A|\uFF1B')

    #english_filter = re.compile(r'\(|\)|\#|\+|\=|\?|\!|\;|\,|\"|\:')#|\.

    if language == "ar":
        return re.subn(arabic_filter, '', utterance)[0]
    elif language == "en" or language == "de" or language == "es" or language == "tr":
        return re.subn(english_filter, '', utterance)[0].lower()
    elif language == "uk":
        return re.subn(cyrillic_filter, '', utterance)[0].lower()
    elif language == "zh" or language == "ja":
        return re.subn(japanese_filter, '', utterance)[0]
    else:
        raise ValueError(f'Text normalization for {language} is not supported')

def tokenize_for_mer(text):
    reg_range = r"[\u4e00-\ufaff]|[0-9]+|[a-zA-Z]+\'*[a-z]*"
    matches = re.findall(reg_range, text, re.UNICODE)
    p = inflect.engine()
    res = []
    for item in matches:
        try:
            temp = p.number_to_words(item) if (item.isnumeric() and len(regex.findall(r'\p{Han}+', item)) == 0) else item
        except:
            temp = item
        res.append(temp)
    return res

def remove_special_characters(text):
    if chars_to_ignore_re is not None:
        return re.sub(chars_to_ignore_re, "", text).lower()
    else:
        return text.lower()



CHARS_TO_IGNORE = [",", "?", "¿", ".", "!", "¡", ";", "；", ":", '""', "%", '"', "�", "ʿ", "·", "჻", "~", "՞",
                   "؟", "،", "।", "॥", "«", "»", "„", "“", "”", "「", "」", "‘", "’", "《", "》", "(", ")",
                   "{", "}", "=", "`", "_", "+", "<", ">", "…", "–", "°", "´", "ʾ", "‹", "›", "©", "®", "—", "→", "。",
                   "、", "﹂", "﹁", "‧", "～", "﹏", "，", "｛", "｝", "（", "）", "［", "］", "【", "】", "‥", "〽",
                   "『", "』", "〝", "〟", "⟨", "⟩", "〜", "：", "！", "？", "♪", "؛", "/", "\\", "º", "−", "^", "ʻ", "ˆ"]
chars_to_ignore_re = f"[{re.escape(''.join(CHARS_TO_IGNORE))}]"




DebugFlag = False
hypos=list()
targets=list()

parser = argparse.ArgumentParser()
parser.add_argument("-d", "--debug", action="store_true")
parser.add_argument("srcLang")
parser.add_argument("tgtLang")
parser.add_argument("hypTsvFile")
parser.add_argument("refTsvFile")
args = parser.parse_args()
srcL  = args.srcLang
tgtL  = args.tgtLang
hypF  = args.hypTsvFile
refF  = args.refTsvFile
if args.debug:
    DebugFlag = True

hypDict = loadTsvEntries(hypF)
refDict = loadTsvEntries(refF)

hypos = hypDict.values()
targets = refDict.values()

refs_split = list()
hypos_split = list()
refs_wer = list()
refs_taged = list()
hyps_wer = list()
import opencc
converter = opencc.OpenCC('t2s')
for ref, hyp in zip(targets, hypos):
    ref_w = ref.replace("<tag", "").replace(">", "")
    hyp_w = hyp.replace("<tag", "").replace(">", "")
    ref_w = remove_special_characters(ref_w)
    hyp_w = remove_special_characters(hyp_w)
    refs_wer.append(ref_w)
    hyps_wer.append(hyp_w)
    ref_taged = ref.replace("<tag", "startoftag").replace(">", "endoftag") 
    ref_taged = remove_special_characters(ref_taged)
    ref_taged = ref_taged.replace("startoftag", "<tag").replace("endoftag", ">")
    refs_taged.append(ref_taged)
    ref = converter.convert(ref)
    hyp = converter.convert(hyp)
    ref = remove_special_characters(ref)
    hyp = remove_special_characters(hyp)
    refs_split.append(" ".join(tokenize_for_mer(ref)))
    hypos_split.append(" ".join(tokenize_for_mer(hyp)))

try:
    error = pier(refs_taged, hyps_wer)
    scores = {"PIER": error['poi']['PIER']}
    print(json.dumps({
        "state": "OK",
        "scores": scores
    }))
except Exception as e:
    print(json.dumps({
        "state": "ERROR",
        "reason": str(e)
    }))


'''
error = pier(refs_taged, hyps_wer, split_hyphen=True)
print(f'PIER-2 {error}')

out = jiwer.process_words(refs_wer, hyps_wer)
with open("w.eval.txt", "w") as f:
    f.write(jiwer.visualize_alignment(out, skip_correct=False))
'''
