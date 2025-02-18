#! /bin/bash

#SBATCH -A plgmeetween2025-cpu
#SBATCH -p plgrid
#SBATCH -N 1
#SBATCH --ntasks-per-node=1
#SBATCH --mem=1G
#SBATCH --job-name=sqaa
#SBATCH --time 72:00:00

# -----------
# manage args
# -----------

print_if_verbose() {
  if test $verbose -eq 1 ; then echo "$@" 1>&2 ; fi
}

show_help() {
  cat << EOF
ARGS: [-h] [-v] lang hypFile refFile
  where
      -h        print help
      -v        verbose
      lang      two-digit language code
      hypFile   json file with answer predictions
      refFile   json file with questtion-answer references
EOF
}


# A POSIX variable
OPTIND=1         # Reset in case getopts has been used previously in the shell.

# Initialize our own variables:
verbose=0
debugInfo=""

while getopts "hv" opt; do
  case "$opt" in
    h)
      show_help
      exit 0
      ;;
    v)
      verbose=1
      debugInfo='-d'
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

tmpPrefix=/tmp/rSa.$$
outTmp=${tmpPrefix}.out
tmpScores=${tmpPrefix}.scores
tmpFinal=${tmpPrefix}.final

source ${PLG_GROUPS_STORAGE}/plggmeetween/envs/setup/groq.USE

## exe=/net/people/plgrid/plgcattoni/eval/SQA/run-SQA-accuracy.py
exe=${PLG_GROUPS_STORAGE}/plggmeetween/envs/etc/SQA-accuracy/run-SQA-accuracy.py

python $exe $debugInfo -p $hyp -r $ref -o $outTmp 2>/dev/null 1>$tmpScores

if test $? != 0
then
  exitFlag=1
  state=ERROR
  reason=UNKNOWN
  score=UNKNOWN
  printf '{"state": "%s", "reason": "%s", "scores": {"accuracy"": "%s"}}\n' $state $reason $score 
else
  exitFlag=0
  state=OK
  printf '{"state": "%s", "scores": ' $state > $tmpFinal
  printf '%s' "$(<$tmpScores)" >> $tmpFinal
  echo '}' >> $tmpFinal
fi

cat $tmpFinal

\rm -f ${tmpPrefix}.*

