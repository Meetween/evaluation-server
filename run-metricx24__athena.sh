#! /bin/bash

#SBATCH -A plgmeetween2026-gpu-a100
#SBATCH -p plgrid-gpu-a100
#SBATCH -N 1
#SBATCH --ntasks-per-node=1
#SBATCH --gres=gpu:1
#SBATCH --mem=30G
#SBATCH --job-name=metricx24


# -----------
# manage args
# -----------

show_help() {
  cat << EOF
ARGS: [-h] srcL tgtL srcFile hypFile refFile
  where
      -h	print help
EOF
}


exit_with_error() {
  reason="$@"
  printf "{\"state\": \"ERROR\", \"reason\": \"${reason}\"}\n"
  exit 1
}


resegment_hyp_file() {
  hypIn=$1
  refIn=$2
  hypOut=$3
  lang=$4

  resExe=${PLG_GROUPS_STORAGE}/plggmeetween/evaluation/DO_source_resegmenter.sh

  $resExe $lang $hypIn $refIn > $hypOut
}


# A POSIX variable
OPTIND=1         # Reset in case getopts has been used previously in the shell.

# Initialize our own variables:
debugFlag=0
resegment=1

while getopts "hd" opt; do
  case "$opt" in
    h)
      show_help
      exit 0
      ;;
    d)
      debugFlag=1
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

test -f "$srcF" || { exit_with_error cannot find srcFile $srcF ; }
test -f "$hypF" || { exit_with_error cannot find hypFile $hypF ; }
test -f "$refF" || { exit_with_error cannot find refFile $refF ; }

# do not resegment if num lines of $hypF equals num lines of $refF
if test $(wc -l < $hypF) == $(wc -l < $refF) ; then resegment=0 ; fi


# source the proper env
source ${PLG_GROUPS_STORAGE}/plggmeetween/envs/setup/metricx.USE

exe1=${PLG_GROUPS_STORAGE}/plggmeetween/envs/etc/metricx/generateJsonl.py

tmpD=$(mktemp -d)
tmpHyp=${tmpD}/hyp
tmpInJ=${tmpD}/inJsonl
tmpOutJ=${tmpD}/outJsonl
tmpErr=${tmpD}/err

# perform mwersegmentation if resegment == 1
if test $resegment == 1
then
  resegment_hyp_file $hypF $refF $tmpHyp $tgtL
  ## echo YES resegmentation $(wc -l < $hypF) $(wc -l < $refF) $(wc -l < $tmpHyp)
else
  cat $hypF > $tmpHyp
  ## echo NO resegmentation $(wc -l < $hypF) $(wc -l < $refF) $(wc -l < $tmpHyp)
fi


# create the input jsonL containing the src, hyp and ref sentences
python3 $exe1 $srcF $tmpHyp $refF $tmpInJ 2> ${tmpErr}
if test $? != 0 ; then exit_with_error "$(basename $exe1) failure" ; fi

# create the output jsonL with the scores (one per sentence)
python3 -m metricx24.predict \
		--tokenizer google/mt5-xl \
		--model_name_or_path google/metricx-24-hybrid-xl-v2p6 \
		--max_input_length 1536 \
		--batch_size 1 \
		--input_file $tmpInJ \
		--output_file $tmpOutJ \
    2> ${tmpErr}
if test $? != 0 ; then exit_with_error "metricx24.predict failure" ; fi


# estract the scores, compute the mean and print it
pc=$(cat <<EOF
import sys, json
for line in sys.stdin:
  obj=json.loads(line.rstrip())
  print(obj["prediction"])
EOF
)
python3 -c "$pc" < $tmpOutJ \
   | awk '{s+=$1} END {printf "{\"state\": \"OK\", \"scores\": {\"metricx24\": %f}}\n", s/NR}'


\rm -rf ${tmpD}


