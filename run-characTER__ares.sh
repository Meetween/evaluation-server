#! /bin/bash

#SBATCH -A plgmeetween2025-cpu
#SBATCH -p plgrid
#SBATCH -N 1
#SBATCH --ntasks-per-node=1
#SBATCH --mem=50G
#SBATCH --job-name=characTER

# script for the evaluation with CharacTER metric

preprocessFile() {
  tr -d '[:punct:]' | tr '[:upper:]' '[:lower:]'
}

# -----------
# manage args
# -----------

show_help() {
  cat << EOF
ARGS: [-h] [-n] [-p] [-v] lang hypFile refFile
  where
      -h        print help
      -v        verbose
      -n        do NOT perform re-segmentation of hypFile
      -p        preprocess hypFile and refFile (delete punctuation and put in lowercase)
EOF
}


# A POSIX variable
OPTIND=1         # Reset in case getopts has been used previously in the shell.

# Initialize our own variables:
resegment=1
preprocess=0
verbose=0

while getopts "hnpv" opt; do
  case "$opt" in
    h)
      show_help
      exit 0
      ;;
    n)
      resegment=0
      ;;
    p)
      preprocess=1
      ;;
    v)
      verbose=1
      ;;
  esac
done

shift $((OPTIND-1))

[ "${1:-}" = "--" ] && shift

lang=$1
hyp=$2
ref=$3
shift 3

test -f "$hyp" || { echo cannot find hyp $hyp ; exit 1 ; }
test -f "$ref" || { echo cannot find ref $ref ; exit 1 ; }

source ${PLG_GROUPS_STORAGE}/plggmeetween/envs/setup/characTER.USE
evalExe=${PLG_GROUPS_STORAGE}/plggmeetween/envs/etc/CharacTER/CharacTER.py

resExe=${PLG_GROUPS_STORAGE}/plggmeetween/envs/etc/mwerSegmenter/DO_apply_mwerSegmenter.sh

tmpPrefix=/tmp/rct.$$
tmpHyp=${tmpPrefix}.hyp
tmpRef=${tmpPrefix}.ref
tmpBuf=${tmpPrefix}.buf
tmpLog=${tmpPrefix}.LOG

# perform preprocessing if preprocess == 1
if test $preprocess == 1
then
  preprocessFile < $ref > $tmpRef
  preprocessFile < $hyp > $tmpHyp
else
  cat $hyp > $tmpHyp
  cat $ref > $tmpRef
fi

# perform mwersegmentation if resegment == 1
if test $resegment == 1
then
  $resExe $tmpHyp $tmpRef $tmpBuf
  cat $tmpBuf > $tmpHyp
fi

$evalExe -r $tmpRef -o $tmpHyp &> ${tmpLog}
# manage errors                                                                 
if test $? != 0
then
  exitFlag=1
  state=ERROR
  reason=$(grep 'lines in the hypothesis file' $tmpLog | perl -pe 's/Error! //')
  score=UNKNOWN
  printf '{"state": "%s", "reason": "%s", "scores": {"characTER": "%s"}}\n' $state "$reason" $score
else
  exitFlag=0
  state=OK
  score=$(cat $tmpLog)
  printf '{"state": "%s", "scores": {"characTER": %s}}\n' $state $score
fi

rm -f ${tmpPrefix}.*

exit $exitFlag

