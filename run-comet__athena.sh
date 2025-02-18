#! /bin/bash

#SBATCH -A plgmeetween2025-gpu-a100
#SBATCH -p plgrid-gpu-a100
#SBATCH -N 1
#SBATCH --ntasks-per-node=1
#SBATCH --gres=gpu:1
#SBATCH --mem=50G
#SBATCH --job-name=comet

# script for the evaluation of translation quality


# -----------
# manage args
# -----------

show_help() {
  cat << EOF
ARGS: [-h] [-n] srcFile hypFile refFile
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

src=$1
hyp=$2
ref=$3
shift 3

test -f "$src" || { echo cannot find srcFile $src ; exit 1 ; }
test -f "$hyp" || { echo cannot find hypFile $hyp ; exit 1 ; }
test -f "$ref" || { echo cannot find refFile $ref ; exit 1 ; }

source ${PLG_GROUPS_STORAGE}/plggmeetween/envs/setup/comet.USE

resExe=${PLG_GROUPS_STORAGE}/plggmeetween/envs/etc/mwerSegmenter/DO_apply_mwerSegmenter.sh

tmpPrefix=/tmp/rb.$$
tmpScores=${tmpPrefix}.scores
tmpHyp=${tmpPrefix}.hyp

# perform mwersegmentation if resegment == 1
if test $resegment == 1
then
  $resExe $hyp $ref $tmpHyp
  ## echo YES resegmentation $(wc -l < $hyp) $(wc -l < $ref) $(wc -l < $tmpHyp)
else
  cat $hyp > $tmpHyp
  ## echo NO resegmentation $(wc -l < $hyp) $(wc -l < $ref) $(wc -l < $tmpHyp)
fi

comet-score --quiet --only_system -s $src -t $tmpHyp -r $ref 2>/dev/null > $tmpScores

if test $? != 0
then
  exitFlag=1
  state=ERROR
  reason=UNKNOWN
  score=UNKNOWN
  printf '{"state": "%s", "reason": "%s", "scores": {"comet": "%s"}}\n' $state $reason $score
else
  exitFlag=0
  state=OK
  score=$(cat $tmpScores | awk '{printf $3}')
  printf '{"state": "%s", "scores": {"comet": %s}}\n' $state $score
fi


rm -f ${tmpPrefix}.*


