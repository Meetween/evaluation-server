"""
VoxPopuli gender gap evaluation script.
Computes gender-based ASR performance disparities using bootstrap sampling and statistical tests.
"""

import json
import os
import time

import fire
import jiwer
import numpy as np
import pandas as pd
import scipy
import random
import pprint
try:
    import cyrtranslit
    HAS_CYRTRANSLIT = True
except ImportError:
    HAS_CYRTRANSLIT = False
from joblib import Parallel, delayed
import tempfile
import shutil
import sys


def compute_metrics_row(metric, reference, transcription, lang, normalize: bool):
    """Compute WER or CER for a single sentence pair."""
    if metric == "wer":
        return jiwer.wer(reference, transcription)
    elif metric == "cer":
        return jiwer.cer(reference, transcription)
    else:
        raise ValueError(f"Unknown metric {metric}")


def compute_metrics(df, lang, whisper_normalize_text: bool = False):
    """Compute aggregate WER across all samples in a dataframe."""
    if len(df["reference"]):
        references = df["reference"].tolist()
        transcriptions = df["transcription"].tolist()

        return {
            "wer": jiwer.wer(references, transcriptions),
        }
    else:
        return {"wer": np.nan}


def find_users_below_percentile(df, minority_accept_percentile):
    spu_array = df["client_id"].value_counts()
    perc_abs_threshold = np.percentile(spu_array.values, minority_accept_percentile)
    selected_users = spu_array.loc[spu_array <= perc_abs_threshold]
    return set(selected_users.index)


def add_prefix_to_keys(d, prefix):
    return {f"{prefix}_{k}": v for k, v in d.items()}


def add_frequency_weight(df):
    """Compute the relative frequency for each user, it'll be needed for stratification."""
    w = df["client_id"].value_counts(normalize=True)
    w.name = "weight"
    return df.join(w, on="client_id")


def sample_and_compute_metrics(
    minority_df, majority_df, minority_perc_sampled, lang
):
    """Sample equal-sized groups and compute WER metrics."""
    smallest_df = minority_df if len(minority_df) < len(majority_df) else majority_df
    per_group_sample_size = int(minority_perc_sampled * len(smallest_df))
    curr_min_df = minority_df.sample(n=per_group_sample_size, weights="weight")
    curr_maj_df = majority_df.sample(n=per_group_sample_size, weights="weight")
    sample_size = 2 * per_group_sample_size

    maj_metrics = compute_metrics(curr_maj_df, lang, False)
    min_metrics = compute_metrics(curr_min_df, lang, False)
    mean_metrics = compute_metrics(
        pd.concat([curr_maj_df, curr_min_df]), lang, False
    )

    return {
        "min_wer": min_metrics["wer"],
        "maj_wer": maj_metrics["wer"],
        "subsample_wer": mean_metrics["wer"],
        "subsample_size": sample_size,
    }


def main(
    lang,
    evaluation_file: str,
    apply_sampling_minority: bool = True,
    apply_sampling_majority: bool = True,
    num_proc: int = 4,
    minority_accept_percentile: float = 99,
    n_iterations: int = 1000,
    minority_perc_sampled: float = 0.4,
    overwrite_results: bool = False,
    do_sampling: bool = True,
):
    # Hard-coded for gender gap evaluation
    target_col = "gender"
    minority_group = "female"
    majority_group = "male"

    # 1. Load transcriptions from result file...

    eval_df = pd.read_csv(evaluation_file, sep="\t", encoding="utf-8")

    # Ensure client_id column exists (VoxPopuli uses speaker_id)
    if "speaker_id" in eval_df.columns and "client_id" not in eval_df.columns:
        eval_df["client_id"] = eval_df["speaker_id"]

    # init stuff
    random.seed(42)
    np.random.seed(42)
    output_dir = tempfile.mkdtemp()
    os.makedirs(f"{output_dir}/empty_stats", exist_ok=True)
    os.makedirs(f"{output_dir}/samples", exist_ok=True)
    
    # 4. Some references might be empty due to issues in the original dataset. We filter them out, too.
    init_len = len(eval_df)
    eval_df = eval_df.loc[~eval_df["reference"].isna()]
    final_len = len(eval_df)
    if (final_len - init_len) > 0:
        print(f"Filtering out {final_len - init_len} samples with empty references", file=sys.stderr)

    # Let's also count how many empty transcriptions we have. But we do not filter them out.
    empty_transcriptions = len(eval_df.loc[eval_df["transcription"].isna()])
    if empty_transcriptions > 0:
        print(f'Empty transcriptions found: {empty_transcriptions}', file=sys.stderr)
    eval_df["transcription"] = eval_df["transcription"].fillna("")

    empty_stats = {
        "reference": final_len - init_len,
        "transcription": empty_transcriptions,
    }
    with open(
        f"{output_dir}/empty_stats/empty_stats_{lang}_{target_col}_{majority_group}_{minority_group}.json",
        "w",
    ) as fp:
        json.dump(empty_stats, fp, indent=2)

    # bonus. if it's serbian or russian, transliterate everything into cyrillic
    if lang == "sr" or lang == "ru":
        if not HAS_CYRTRANSLIT:
            print(f"WARNING: cyrtranslit not installed. Cannot transliterate {lang}",
                  file=sys.stderr)
        else:
            print(f"Transliterating to cyrillic {lang}", file=sys.stderr)
            eval_df["transcription"] = eval_df["transcription"].apply(
                lambda x: cyrtranslit.to_cyrillic(x, lang)
            )
            eval_df["reference"] = eval_df["reference"].apply(
                lambda x: cyrtranslit.to_cyrillic(x, lang)
            )

    # 5. separate majority (advantaged) and minority (disadvantaged) groups
    minority_df = eval_df.loc[eval_df[target_col] == minority_group]
    majority_df = eval_df.loc[eval_df[target_col] == majority_group]

    # 6. compute metrics on the whole split
    results = dict()

    if do_sampling:
        # 6. select users based on SPU percentile
        if apply_sampling_minority:
            mino_users = find_users_below_percentile(
                minority_df, minority_accept_percentile
            )
        else:
            mino_users = minority_df["client_id"].unique()
        if apply_sampling_majority:
            majo_users = find_users_below_percentile(
                majority_df, minority_accept_percentile
            )
        else:
            majo_users = majority_df["client_id"].unique()

        minority_df = minority_df.loc[minority_df["client_id"].isin(mino_users)]
        majority_df = majority_df.loc[majority_df["client_id"].isin(majo_users)]

        minority_df, majority_df = map(add_frequency_weight, (minority_df, majority_df))
        min_count, maj_count = len(minority_df), len(majority_df)
        results["largest_group"] = "minority" if min_count > maj_count else "majority"

        overall_maj = majority_df
        overall_min = minority_df

        # Compute sentence-level WER metrics
        sample_df = pd.concat([overall_maj, overall_min])
        wers = []
        for idx, row in sample_df.iterrows():
            wers.append(
                compute_metrics_row(
                    "wer",
                    row["reference"],
                    row["transcription"],
                    lang,
                    False,
                )
            )
        sample_df["wer"] = wers

        sample_df.to_csv(
            f"{output_dir}/samples/sample_{lang}_{target_col}_{majority_group}_{minority_group}.csv"
        )
        results |= add_prefix_to_keys(
            compute_metrics(
                pd.concat([overall_maj, overall_min]), lang, False
            ),
            "overall",
        )

        # Bootstrap iterations: sample and compute metrics multiple times
        samples = Parallel(n_jobs=num_proc, verbose=0)(
            delayed(sample_and_compute_metrics)(
                overall_min,
                overall_maj,
                minority_perc_sampled,
                lang,
            )
            for _ in range(n_iterations)
        )

        stats = pd.DataFrame(samples)  # type: ignore

        mean_stats = stats.mean()
        std_stats = stats.std()

        # Relative difference metrics (from paper Eq. 1)
        # E(rA,rB) = 100 * (phi(rA) - phi(rB)) / phi(rB)
        relative_wer_diffs = []
        
        for idx in range(len(stats)):
            if stats.iloc[idx]["maj_wer"] > 0:
                rel_wer = 100.0 * (stats.iloc[idx]["min_wer"] - stats.iloc[idx]["maj_wer"]) / stats.iloc[idx]["maj_wer"]
                relative_wer_diffs.append(rel_wer)
        
        if relative_wer_diffs:
            results["wer_diff_rel_mean"] = np.mean(relative_wer_diffs)
            results["wer_diff_rel_std"] = np.std(relative_wer_diffs)
        else:
            results["wer_diff_rel_mean"] = None
            results["wer_diff_rel_std"] = None

        # stats on the subsample
        results["subsample_size"] = samples[0]["subsample_size"]

        # two-sided t-test on WER
        ttest_two_sided = scipy.stats.ttest_ind(stats["min_wer"], stats["maj_wer"])
        results["ttest_wer_pvalue_2sided"] = ttest_two_sided.pvalue

    # Keep only essential metrics for output
    essential_results = {
        "wer_diff_rel_mean": results.get("wer_diff_rel_mean"),
        "wer_diff_rel_std": results.get("wer_diff_rel_std"),
        "ttest_wer_pvalue_2sided": results.get("ttest_wer_pvalue_2sided"),
    }

    print(json.dumps({
        "state": "OK",
        "scores": essential_results
    }))
    shutil.rmtree(output_dir)


if __name__ == "__main__":
    fire.Fire(main)
