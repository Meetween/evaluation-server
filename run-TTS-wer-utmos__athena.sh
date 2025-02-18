#! /bin/bash

#SBATCH -A plgmeetween2025-gpu-a100
#SBATCH -p plgrid-gpu-a100
#SBATCH -N 1
#SBATCH --ntasks-per-node=1
#SBATCH --gres=gpu:1
#SBATCH --mem=10G
#SBATCH --job-name=tts
#SBATCH --time 24:00:00

# script for the evaluation of TTS
#  1) args: wav_dir ref_tsv
#  2) transcribe with wishper the waves and compute the WER wrt the ref_tsv
#  3) compute UTMOS on each wav and get the average


# get the wer score from a json string (e.g. '{"scores": {"wer": 1.2345}}')
get_wer_score_from_json() {
  python -c "import sys, json; obj=json.load(sys.stdin) ; print(obj['scores']['wer'])"
}

# get mean and standard_deviation from a file with numbers
get_mean_stdev() {
  python ${PLG_GROUPS_STORAGE}/plggmeetween/envs/etc/get_mean_stdev.py
}

# -----------
# manage args
# -----------

show_help() {
  cat << EOF
ARGS: [-h] lang wav_dir ref_tsv
  where
      -h	print help
      -v	verbose
EOF
}


# A POSIX variable
OPTIND=1         # Reset in case getopts has been used previously in the shell.

# Initialize our own variables:
verbose=0

while getopts "hv" opt; do
  case "$opt" in
    h)
      show_help
      exit 0
      ;;
    v)
      verbose=1
      ;;
  esac
done

shift $((OPTIND-1))

[ "${1:-}" = "--" ] && shift

lang=$1
wavD=$2
refF=$3
shift 3

test -d "$wavD" || { echo cannot find wav_dir $wavD ; exit 1 ; }
test -f "$refF" || { echo cannot find ref_tsv $refF ; exit 1 ; }


tmpPrefix=/tmp/rtwu.$$


# ----------------------------
# transcribe with wishper the waves

source ${PLG_GROUPS_STORAGE}/plggmeetween/envs/setup/whisper.USE

traDir=${tmpPrefix}.transcriptions
singleRef=${tmpPrefix}.ref
werListFile=${tmpPrefix}.wer

exe1=whisper
model=large
task=transcribe

args="--task $task --language $lang --model $model"
args="$args --output_format txt --output_dir $traDir"

exe2=${PLG_GROUPS_STORAGE}/plggmeetween/evaluation/run-wer__ares.sh


# ----------------------------
# compute the WER score for all the transcriptions (mean and standard deviation)

: > $werListFile
for w in ${wavD}/*.wav
do
  b=$(basename $w .wav)
  if test $verbose -eq 1 ; then
    echo doing $exe1 $w $args 1>&2
  fi
  $exe1 $w $args &>/dev/null
  traF=${traDir}/${b}.txt
  # computing single WER
  grep "$b" $refF | cut -f2 > $singleRef
  bash $exe2 -g $lang $traF $singleRef | get_wer_score_from_json >> $werListFile
  if test $verbose -eq 1 ; then
    echo wer $(tail -1 $werListFile) 1>&2
  fi
done

werInfo=$(get_mean_stdev < $werListFile)
wMean=$(echo $werInfo | awk '{print $1}')
wStdev=$(echo $werInfo | awk '{print $2}')


# ----------------------------
# compute the UTMOS score for all the wav files (mean and standard deviation)

exe3=${PLG_GROUPS_STORAGE}/plggmeetween/envs/etc/UTMOS/compute_utmos_from_dir.sh

utmosInfo=$($exe3 $wavD)
uMean=$(echo $utmosInfo | awk '{print $1}')
uStdev=$(echo $utmosInfo | awk '{print $2}')


# -------------------------------
# print the scores in json format
#
exitFlag=0
state=OK
printf '{"state": "%s", "scores": {"wer": {"mean": "%s", "standard_deviation": "%s"}, "utmos": {"mean": "%s", "standard_deviation": "%s"}}}\n' $state $wMean $wStdev $uMean $uStdev

# -----------
# clean files

\rm -rf  ${traDir} $singleRef $werListFile $tmpPrefix


