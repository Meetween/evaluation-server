#! /bin/bash

#SBATCH -A plgmeetween2026-gpu-a100
#SBATCH -p plgrid-gpu-a100
#SBATCH -N 1
#SBATCH --ntasks-per-node=1
#SBATCH --gres=gpu:1
#SBATCH --mem=50G
#SBATCH --job-name=IF26

# script for the evaluation of the IWSLT-2026 Instruction Following task


tmpPrefix=/tmp/rI26.$$

# ---------
# functions
# ---------

get_scores_from_json() {
  python3 -c "import sys, json; obj=json.load(sys.stdin) ; print(json.dumps(obj['scores']))"
}


fill_scores() {
  finalPartialMetricsJson=$1
  jjExe=${PLG_GROUPS_STORAGE}/plggmeetween/envs/etc/jj.py
  tmpEmptyMetricsJsonF=${tmpPrefix}.empty.json
  tmpPartialMetricsJsonF=${tmpPrefix}.partial.json
  #
  # create the tmp json with the empty metrics
  cat - << EOF > $tmpEmptyMetricsJsonF
{"ACHAP-CollarF1": -1, "ACHAP-COMET": -1, "ACHAP-GC-BERTScore": -1, "ACHAP-TM-BERTScore": -1, "ACHAP-TM-MATCHED": -1, "ACHAP-WER": -1, "ASR-WER": -1, "QA-BERTScore": -1, "QE-accuracy": -1, "QE-format-accuracy": -1, "SUM-BERTScore": -1, "TRANS-COMET": -1}  
EOF
  #
  # create the tmp json with the actual partial metrics computed till now and filtered from STDIN
  get_scores_from_json < $finalPartialMetricsJson > $tmpPartialMetricsJsonF
  #
  # join the two json and add the state
  echo '{"state": "OK", "scores": '$($jjExe $tmpEmptyMetricsJsonF $tmpPartialMetricsJsonF)'}'
  #
  # delete the tmp files
  \rm -f $tmpEmptyMetricsJsonF $tmpPartialMetricsJsonF
}


# -----------
# manage args
# -----------

show_help() {
  cat << EOF
ARGS: [-h] [-n] srcL tgtL hypFile refFile
  where
      -h	print help
      -n	do NOT perform re-segmentation of hypFile
EOF
}


# A POSIX variable
OPTIND=1         # Reset in case getopts has been used previously in the shell.

# Initialize our own variables:
resegment=1

while getopts "hn" opt; do
  case "$opt" in
    h)
      show_help
      exit 0
      ;;
    n)
      resegment=0
      ;;
  esac
done

shift $((OPTIND-1))

[ "${1:-}" = "--" ] && shift

test "$#" -ge 4 || { show_help ; exit 1 ; }
scrLang=$1
tgtLang=$2
hypFile=$3
refFile=$4
shift 4

test -f "$hypFile" || { echo cannot find hypFile $hypFile ; exit 1 ; }
test -f "$refFile" || { echo cannot find refFile $refFile ; exit 1 ; }

# source the proper env
source ${PLG_GROUPS_STORAGE}/plggmeetween/envs/setup/ifeval26.USE

# set with the path of the dir with the "mwerSegmenter" exe
export MWERSEGMENTER_ROOT=${PLG_GROUPS_STORAGE}/plggmeetween/envs/etc/mwerSegmenter/bin

# define the exe to be invoked
exe=mcif_eval


track=short
if cat $refFile | grep -i '<task' | grep -i 'track="long"' &>/dev/null  ; then track=long ; fi

tmpOut=${tmpPrefix}.out
$exe -s $hypFile -r $refFile -t $track -l $tgtLang 1> $tmpOut

# add the non-computed metrics (with -1 value) -- required by SPEECHM instances
fill_scores $tmpOut

\rm -f $tmpOut

