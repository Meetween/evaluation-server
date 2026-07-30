import argparse
import json
import os, sys
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from chunkseg import evaluate_batch
from chunkseg.parsers import parse_transcript
from comet import download_model, load_from_checkpoint


CHAR_LEVEL_LANGS = {"zh"}


class MwerSegmenter:
    """
    Executes the mWERSegmenter tool introduced in `"Evaluating Machine Translation Output
    with Automatic Sentence Segmentation" by Matusov et al. (2005)
    <https://aclanthology.org/2005.iwslt-1.19/>`_.

    The tool can be downloaded at:
    https://www-i6.informatik.rwth-aachen.de/web/Software/mwerSegmenter.tar.gz
    """
    def __init__(self, character_level=False):
        self.mwer_command = "DO_apply_mwerSegmenter.sh"
        self.character_level = character_level
        if shutil.which(self.mwer_command) is None:
            mwerSegmenter_root = os.getenv("MWERSEGMENTER_ROOT")
            assert mwerSegmenter_root is not None, \
                f"{self.mwer_command} is not in PATH and no MWERSEGMENTER_ROOT environment " \
                "variable is set"
            self.mwer_command = mwerSegmenter_root + "/DO_apply_mwerSegmenter.sh"

    def __call__(self, prediction: str, reference_sentences: List[str]) -> List[str]:
        """
        Segments the prediction based on the reference sentences using the edit distance algorithm.
        """
        tmp_pred = tempfile.NamedTemporaryFile(mode="w", delete=False)
        tmp_ref = tempfile.NamedTemporaryFile(mode="w", delete=False)
        # the output segmented file
        tmp_outsegm = tempfile.NamedTemporaryFile(mode="w", delete=False)
        if self.character_level:
            # If character-level evaluation, add spaces for resegmentation
            prediction = " ".join(prediction)
            reference_sentences = [" ".join(reference) for reference in reference_sentences]
        try:
            # if the prediction is empty mwerSegmenter returns a segmentation fault, so we put a
            # fake "." to avoid this issue
            if prediction.strip() == "":
                prediction = "."
            tmp_pred.write(prediction)
            tmp_ref.writelines(ref + '\n' for ref in reference_sentences)
            tmp_pred.flush()
            tmp_ref.flush()
            subprocess.run([
                self.mwer_command,
                tmp_pred.name,
                tmp_ref.name,
                tmp_outsegm.name])
            # DO_apply_mwerSegmenter.sh writes into the tmp_outsegm file
            with open(tmp_outsegm.name) as f:
                segments = []
                for line in f.readlines():
                    if self.character_level:
                        # If character-level evaluation, remove only spaces between characters
                        line = re.sub(r'(.)\s', r'\1', line)
                    segments.append(line.strip())
                return segments
        finally:
            tmp_pred.close()
            tmp_ref.close()
            os.unlink(tmp_pred.name)
            os.unlink(tmp_ref.name)
            os.unlink(tmp_outsegm.name)


def read_hypo(hypo_path: Path, language: str) -> Dict[str, str]:

    def read_text(xml_sample):
        if xml_sample.text is None:
            return ""
        return xml_sample.text.strip()

    xml = ET.parse(hypo_path)
    return {sample.attrib['id']: read_text(sample) for sample in xml.getroot().iter("sample")}


def read_reference(ref_path: Path, language: str) -> Dict[str, Dict[str, str]]:
    xml = ET.parse(ref_path)
    refs = {}
    for sample in xml.getroot().iter("sample"):
        s_id = sample.attrib['id']
        s_reference = ''
        s_audio = ''
        s_transcript = ''
        s_translation = ''
        for element in sample.iter():
            if element.tag == "reference":
                s_reference = element.text
            elif element.tag == "audio_path":
                s_audio = element.text
            elif element.tag == "transcript":
                s_transcript = element.text
            elif element.tag == "translation":
                s_translation = element.text
        s_dict = {"reference": s_reference, "audio_path": s_audio,
                  "transcript": s_transcript, "translation": s_translation}
        refs[s_id] = s_dict
    return refs


def _audio_duration(audio_path: str) -> float:
    """Return audio duration in seconds using mutagen (metadata-only, no decoding)."""
    from mutagen import File
    return File(audio_path).info.length


def _align_sections(
        hypo_text: str,
        gold_lines: List[str],
        target_lang: str) -> Tuple[List[str], List[List[int]]]:
    """Align hypothesis sections to gold translation lines via mwerSegmenter."""
    parsed = parse_transcript(hypo_text, "markdown")
    titles = parsed.titles or []
    sections = parsed.sections or []

    if not titles or not sections:
        return titles, [[] for _ in titles]

    section_texts = [" ".join(sents) for sents in sections]
    full_hyp = " ".join(section_texts)

    segmenter = MwerSegmenter(character_level=(target_lang in CHAR_LEVEL_LANGS))
    reseg = segmenter(full_hyp, gold_lines)

    section_ends, pos = [], 0
    for t in section_texts:
        pos += len(t)
        section_ends.append(pos)
        pos += 1

    section_to_line_map: List[List[int]] = [[] for _ in titles]
    hyp_pos, sec_idx = 0, 0
    for i, seg in enumerate(reseg):
        seg = seg.strip()
        if not seg:
            continue
        found = full_hyp.find(seg, hyp_pos)
        mid = found + len(seg) // 2 if found >= 0 else hyp_pos
        if found >= 0:
            hyp_pos = found + len(seg)
        while sec_idx < len(section_ends) - 1 and mid >= section_ends[sec_idx]:
            sec_idx += 1
        section_to_line_map[sec_idx].append(i)

    return titles, section_to_line_map


def _replace_translation_with_transcript(
        hypo_text: str,
        gold_translation: str,
        ref_transcript: str,
        target_lang: str) -> str:
    """Replace translated hypothesis body with reference transcript via mwerSegmenter."""
    gold_lines = [s for s in gold_translation.strip().split("\n") if s.strip()]
    ref_lines = [s for s in ref_transcript.strip().split("\n") if s.strip()]
    assert len(gold_lines) == len(ref_lines), \
        f"Gold translation ({len(gold_lines)}) and transcript ({len(ref_lines)}) " \
        f"line counts differ"

    titles, section_to_line_map = _align_sections(hypo_text, gold_lines, target_lang)
    if not titles:
        return hypo_text

    section_ref = [[ref_lines[i] for i in indices] for indices in section_to_line_map]

    return "\n".join(
        f"# {t}\n{' '.join(r)}\n" for t, r in zip(titles, section_ref)
    ).strip()


def comet_score(data: List[Dict[str, str]]) -> float:
    """
    Computes COMET starting from a List of Dictionary, each containing the "mt", "src", and "ref"
    keys.
    """
    model_path = download_model("Unbabel/wmt22-comet-da")
    model = load_from_checkpoint(model_path)
    model.eval()
    model_output = model.predict(data, batch_size=8, gpus=1)
    return model_output.system_score


def score_achap(
        base_ref_path: Path,
        hypo_dict: Dict[str, str],
        ref_dict: Dict[str, Dict[str, str]],
        lang: str) -> Dict[str, float]:
    """
    Computes chunkseg metrics for audio chaptering (ACHAP):
    - Collar-based F1 (±3s collar): predicted vs reference timestamps with tolerance
    - BERTScore for titles, with two different strategies:
        - Global Concatenation: concatenated predicted vs reference titles
        - Temporally Matched: titles of predicted sections matching reference sections
    - WER: quality measure for the transcript generated alongside

    Hypothesis is a plain Markdown transcript (no timestamps); chunkseg derives
    boundary timestamps and title time associations via forced alignment internally.
    Following the work of:
    `"Beyond Transcripts: A Renewed Perspective on Audio Chaptering"
    <https://www.arxiv.org/abs/2602.08979>`_

    Reference XML format:
      <reference>: JSON [[title, start_seconds], ...]
      <transcript>: English reference transcript
      <translation>: reference translation, line-aligned with transcript
    """
    crosslingual = (lang != "en")
    samples = []
    comet_data = []

    for id, ref_sample in ref_dict.items():
        hypo_text = hypo_dict[id]
        reference = ref_sample["reference"]
        ref_chapters = json.loads(ref_sample["reference"])  # [[title, start_sec], ...]
        ref_titles = [(t, float(s)) for t, s in ref_chapters]
        ref_boundaries = [float(s) for _, s in ref_chapters]
        audio_path = base_ref_path / "AUDIOS" / ref_sample["audio_path"]
        duration = _audio_duration(audio_path.absolute().as_posix())
        transcript = ref_sample["transcript"]

        if crosslingual:
            translation = ref_sample["translation"]
            hypo_text = _replace_translation_with_transcript(
                hypo_text, translation, transcript, lang)

            # Prepare COMET data
            gold_lines = [s for s in translation.strip().split("\n") if s.strip()]
            src_lines = [s for s in transcript.strip().split("\n") if s.strip()]
            segmenter = MwerSegmenter(character_level=(lang in CHAR_LEVEL_LANGS))
            parsed = parse_transcript(hypo_dict[ref_sample.sample_ids[0]], "markdown")
            flat = " ".join(" ".join(s) for s in (parsed.sections or []))
            reseg = segmenter(flat, gold_lines)
            for mt, ref, src in zip(reseg, gold_lines, src_lines):
                comet_data.append({"src": src.strip(), "mt": mt.strip(), "ref": ref.strip()})

        print(f'=> id {id} transcript {len(transcript)} reference {reference} ', file=sys.stderr)
        sample = {
            "hypothesis": hypo_text,
            "reference": ref_boundaries,
            "duration": duration,
            "audio": audio_path.absolute().as_posix(),
            "reference_titles": ref_titles,
            "reference_transcript": transcript,
        }
        samples.append(sample)
        print(f'<= done id {id}', file=sys.stderr)

    # set default values
    out = {}
    out["ACHAP-CollarF1"] = -1
    out["ACHAP-TM-BERTScore"] = -1
    out["ACHAP-GC-BERTScore"] = -1
    out["ACHAP-TM-MATCHED"] = -1
    out["ACHAP-WER"] = -1
    out["ACHAP-COMET"] = -1

    if not samples:
        return out

    results = evaluate_batch(
        samples,
        format="markdown",
        src_lang="eng",
        tgt_lang=lang,
        titles=True,
        wer=not crosslingual,
        collar=3.0,
        tolerance=5.0,
    )
    ## print(f'results {results}')

    if "collar_f1" in results:
        out["ACHAP-CollarF1"] = results["collar_f1"]["mean"]
    if "tm_bs_f1" in results:
        out["ACHAP-TM-BERTScore"] = results["tm_bs_f1"]["mean"]
    if "gc_bs_f1" in results:
        out["ACHAP-GC-BERTScore"] = results["gc_bs_f1"]["mean"]
    if "tm_matched" in results:
        out["ACHAP-TM-MATCHED"] = results["tm_matched"]["mean"]
    if crosslingual:
        out["ACHAP-COMET"] = comet_score(comet_data)
    else:
        if "wer" in results:
            out["ACHAP-WER"] = results["wer"]["mean"]

    return out


def main(
        hypo_path: Path,
        ref_path: Path,
        lang: str) -> Dict[str, float]:
    """
    Main function computing all the scores and returning a Dictionary with the scores
    """
    hypo = read_hypo(hypo_path, lang)
    ref = read_reference(ref_path, lang)

    scores = {}
    scores.update(score_achap(ref_path.parent, hypo, ref, lang))

    return scores


def cli_script():
    """
    Script that evaluates the outputs of a system in XML format against the MCIF reference.
    By default, the evaluation is carried out on all the test elements, but the evaluation can be
    limited to the tasks/samples relevant for one modality by means of the --filter-modality param.
    """
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '--hypothesis', '-s', type=str, required=True,
        help="the hypothesis to be scored")
    parser.add_argument(
        '--reference', '-r', type=str, required=True,
        help='the path to the folder containing the test set definition.')
    parser.add_argument(
        '--language', '-l', type=str, required=True,
        help="the target language to evaluate")
    args = parser.parse_args()
    try:
        hypo_path = Path(args.hypothesis)
        ref_path = Path(args.reference)
        scores = main(
            hypo_path,
            ref_path,
            args.language)
        print(json.dumps({
            "state": "OK",
            "scores": scores
        }))
    except AssertionError as e:  # noqa
        print(json.dumps({
            "state": "ERROR",
            "reason": str(e)
        }))


if __name__ == "__main__":
    cli_script()
