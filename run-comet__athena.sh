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
ARGS: [-h] [-n] srcL tgtL srcFile hypFile refFile
  where
      -h	print help
      -n	do NOT perform re-segmentation of hypFile
EOF
}

resegment_hyp_file() {
  hypIn=$1
  refIn=$2
  hypOut=$3
  lang=$4

  resExe=${PLG_GROUPS_STORAGE}/plggmeetween/envs/etc/mwerSegmenter/DO_apply_mwerSegmenter.sh
  segChars=${PLG_GROUPS_STORAGE}/plggmeetween/envs/etc/segment_chars.py
  unsChars=${PLG_GROUPS_STORAGE}/plggmeetween/envs/etc/unsegment_chars.py


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
      | python3 ${segChars} \
      > $tmpBufHyp

    cat $refIn \
      | sed -e "s/&apos;/'/g" -e 's/&#124;/|/g' -e "s/&amp;/&/g" -e 's/&lt;//g' -e 's/&gt;//g' -e 's/&quot;/"/g' -e 's/&#91;/[/g' -e 's/&#93;/]/g' -e "s/>//g" -e "s/<//g" -e 's/#//g' \
      | python3 ${segChars} \
      > $tmpBufRef

    $resExe $tmpBufHyp $tmpBufRef $hypOut

    # remove previously introduced spaces
    cat $hypOut | python3 ${unsChars} > $tmpBufHyp
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

test "$#" -ge 5 || { show_help ; exit 1 ; }
scrL=$1
tgtL=$2
srcF=$3
hypF=$4
refF=$5
shift 5

test -f "$srcF" || { echo cannot find srcFile $srcF ; exit 1 ; }
test -f "$hypF" || { echo cannot find hypFile $hypF ; exit 1 ; }
test -f "$refF" || { echo cannot find refFile $refF ; exit 1 ; }

source ${PLG_GROUPS_STORAGE}/plggmeetween/envs/setup/comet.USE

tmpPrefix=/tmp/rb.$$
tmpScores=${tmpPrefix}.scores
tmpHyp=${tmpPrefix}.hyp

# perform mwersegmentation if resegment == 1
if test $resegment == 1
then
  resegment_hyp_file $hypF $refF $tmpHyp $tgtL
  ## echo YES resegmentation $(wc -l < $hypF) $(wc -l < $refF) $(wc -l < $tmpHyp)
else
  cat $hypF > $tmpHyp
  ## echo NO resegmentation $(wc -l < $hypF) $(wc -l < $refF) $(wc -l < $tmpHyp)
fi

comet-score --quiet --only_system -s $srcF -t $tmpHyp -r $refF 2>/dev/null > $tmpScores

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


