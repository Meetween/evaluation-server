#! /bin/bash

#SBATCH -A plgmeetween2025-gpu-a100
#SBATCH -p plgrid-gpu-a100
#SBATCH -N 1
#SBATCH --ntasks-per-node=1
#SBATCH --gres=gpu:1
#SBATCH --mem=50G
#SBATCH --job-name=BLEURT

# script for the evaluation of translation quality


# -----------
# manage args
# -----------

show_help() {
  cat << EOF
ARGS: [-h] [-n] srcL tgtL hypFile refFile
  where
      -h	print help
      -v	verbose
      -n	do NOT perform re-segmentation of hypFile
EOF
}

resegment_hyp_file() {
  hypIn=$1
  refIn=$2
  hypOut=$3
  lang=$4

  resExe=${PLG_GROUPS_STORAGE}/plggmeetween/envs/etc/mwerSegmenter/DO_apply_mwerSegmenter.sh

  tmpBufHyp=/tmp/rhf.$$.buf.hyp
  tmpBufRef=/tmp/rhf.$$.buf.ref

  charLevelFlag=0
  case $lang in
    zh|ja|ko)
      charLevelFlag=1
      ;;
  esac

  if test $charLevelFlag != 1
  then
    # remove special chars (Jan code)
    cat $hypIn \
      | sed -e "s/&apos;/'/g" -e 's/&#124;/|/g' -e "s/&amp;/&/g" -e 's/&lt;//g' -e 's/&gt;//g' -e 's/&quot;/"/g' -e 's/&#91;/[/g' -e 's/&#93;/]/g' -e "s/>//g" -e "s/<//g" -e 's/#//g' \
      > $tmpBufHyp

    cat $refIn \
      | sed -e "s/&apos;/'/g" -e 's/&#124;/|/g' -e "s/&amp;/&/g" -e 's/&lt;//g' -e 's/&gt;//g' -e 's/&quot;/"/g' -e 's/&#91;/[/g' -e 's/&#93;/]/g' -e "s/>//g" -e "s/<//g" -e 's/#//g' \
      > $tmpBufRef

    $resExe $tmpBufHyp $tmpBufRef $hypOut
  else
    # remove special chars (Jan code) and segment in individual chars
    cat $hypIn \
      | sed -e "s/&apos;/'/g" -e 's/&#124;/|/g' -e "s/&amp;/&/g" -e 's/&lt;//g' -e 's/&gt;//g' -e 's/&quot;/"/g' -e 's/&#91;/[/g' -e 's/&#93;/]/g' -e "s/>//g" -e "s/<//g" -e 's/#//g' \
      | perl -pe 's/(.)/$1 /g' \
      > $tmpBufHyp

    cat $refIn \
      | sed -e "s/&apos;/'/g" -e 's/&#124;/|/g' -e "s/&amp;/&/g" -e 's/&lt;//g' -e 's/&gt;//g' -e 's/&quot;/"/g' -e 's/&#91;/[/g' -e 's/&#93;/]/g' -e "s/>//g" -e "s/<//g" -e 's/#//g' \
      | perl -pe 's/(.)/$1 /g' \
      > $tmpBufRef

    $resExe $tmpBufHyp $tmpBufRef $hypOut

    # remove ipreviously introduced spaces
    cat $hypOut | perl -pe 's/ (.)/$1/g' > $tmpBufHyp
    cat $tmpBufHyp > $hypOut

  fi

  \rm -f $tmpBufHyp $tmpBufRef
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

sl=$1
tl=$2
hyp=$3
ref=$4
shift 4

test -f "$hyp" || { echo cannot find hyp $hyp ; exit 1 ; }
test -f "$ref" || { echo cannot find ref $ref ; exit 1 ; }

source ${PLG_GROUPS_STORAGE}/plggmeetween/envs/setup/bleurt.USE

ckpDir=${PLG_GROUPS_STORAGE}/plggmeetween/envs/setup/BLEURT-20

tmpPrefix=/tmp/rb.$$
tmpScores=${tmpPrefix}.scores
tmpHyp=${tmpPrefix}.hyp

# perform mwersegmentation if resegment == 1
if test $resegment == 1
then
  resegment_hyp_file $hyp $ref $tmpHyp $tl
  ## echo YES resegmentation $(wc -l < $hyp) $(wc -l < $ref) $(wc -l < $tmpHyp)
else
  cat $hyp > $tmpHyp
  ## echo NO resegmentation $(wc -l < $hyp) $(wc -l < $ref) $(wc -l < $tmpHyp)
fi

python -m bleurt.score_files -candidate_file=$tmpHyp -reference_file=$ref  -bleurt_batch_size=100 -batch_same_length=True -bleurt_checkpoint=$ckpDir -scores_file=$tmpScores &> /dev/null

if test $? != 0
then
  exitFlag=1
  state=ERROR
  reason=UNKNOWN
  score=UNKNOWN
  printf '{"state": "%s", "reason": "%s", "scores": {"bleurt": "%s"}}\n' $state $reason $score
else
  exitFlag=0
  state=OK
  score=$(cat $tmpScores | awk '{t+=$1; n++}END{printf "%s", t/n}')
  printf '{"state": "%s", "scores": {"bleurt": %s}}\n' $state $score
fi

rm -f ${tmpPrefix}.*


