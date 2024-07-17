#! /bin/bash

#SBATCH -A plgmeetween2004-cpu
#SBATCH -p plgrid
#SBATCH -N 1
#SBATCH --ntasks-per-node=1
#SBATCH --mem=50G
#SBATCH --job-name=sacrebleu

# script for the evaluation of translation quality

# -----------
# manage args
# -----------

show_help() {
  cat << EOF
ARGS: [-h] [-n] srcL tgtL hypFile refFile
  where
      -h        print help
      -v        verbose
      -n        do NOT perform re-segmentation of hypFile
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

sl=$1
tl=$2
hyp=$3
ref=$4
shift 4

test -f "$hyp" || { echo cannot find hyp $hyp ; exit 1 ; }
test -f "$ref" || { echo cannot find ref $ref ; exit 1 ; }

source ${PLG_GROUPS_STORAGE}/plggmeetween/envs/setup/sacrebleu.USE
resExe=${PLG_GROUPS_STORAGE}/plggmeetween/envs/etc/mwerSegmenter/DO_apply_mwerSegmenter.sh

tmpPrefix=/tmp/rb.$$
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

## echo "doing BLEU/ChrF/TER $sl $tl $hyp $ref" 1>&2

info=$(sacrebleu -m bleu chrf ter --language-pair $sl-$tl  --score-only --width 2 $ref -i=$tmpHyp | tr '\012' ' ' | tr -d '[],')
# manage errors                                                                 
exitFlag=0
if test -z "$info"
then
  exitFlag=1
  echo '{"bleu": "ERROR", "chrf": "ERROR", "ter": "ERROR"}'
else
  exitFlag=0
  bleu=$(echo $info | awk '{print $1}')
  chrf=$(echo $info | awk '{print $2}')
  ter=$(echo $info | awk '{print $3}')
  printf '{"bleu": %s, "chrf": %s, "ter": %s}\n' $bleu $chrf $ter
fi

rm -f $tmpHyp

exit $exitFlag



