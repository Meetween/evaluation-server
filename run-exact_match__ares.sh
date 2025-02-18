#! /bin/bash

#SBATCH -A plgmeetween2025-cpu
#SBATCH -p plgrid
#SBATCH -N 1
#SBATCH --ntasks-per-node=1
#SBATCH --mem=1G
#SBATCH --job-name=em
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
      lang      two digit language code
      hypFile   txt file with hypotheses (one per line)
      refFile   txt file with references (one per line)
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

source ${PLG_GROUPS_STORAGE}/plggmeetween/envs/setup/evaluate.USE

exe=${PLG_GROUPS_STORAGE}/plggmeetween/envs/etc/HF/exact_match.py

tmpPrefix=/tmp/rem.$$
tmpScore=${tmpPrefix}.score

python $exe $debugInfo $hyp $ref 2>/dev/null 1> $tmpScore

if test $? != 0
then
  exitFlag=1
  state=ERROR
  reason=UNKNOWN
  score=UNKNOWN
  printf '{"state": "%s", "reason": "%s", "scores": {"exact_match": "%s"}}\n' $state $reason $score
else
  exitFlag=0
  state=OK
  score=$(cat $tmpScore | awk '{print $2}' | tr -d '}')
  printf '{"state": "%s", "scores": {"exact_match": %s}}\n' $state $score
fi

\rm -f $tmpScore




