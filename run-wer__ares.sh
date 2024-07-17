#! /bin/bash

#SBATCH -A plgmeetween2004-cpu
#SBATCH -p plgrid
#SBATCH -N 1
#SBATCH --ntasks-per-node=1
#SBATCH --mem=10G
#SBATCH --job-name=wer

# -----------
# manage args
# -----------

preprocessFile() {
  tr -d '[:punct:]' | tr '[:upper:]' '[:lower:]'
}

print_if_verbose() {
  if test $verbose -eq 1 ; then echo "$@" 1>&2 ; fi
}

show_help() {
  cat << EOF
ARGS: [-g] [-h] [-v] lang hypFile refFile
  where
      -g        apply a global minimal alignment between reference and hypothesis sentences before computing the WER
      -h        print help
      -v        verbose
EOF
}


# A POSIX variable
OPTIND=1         # Reset in case getopts has been used previously in the shell.

# Initialize our own variables:
verbose=0
globalFlag=''

while getopts "ghv" opt; do
  case "$opt" in
    g)
      globalFlag='-g'
      ;;
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

sl=$1
hyp=$2
ref=$3
shift 3

test -f "$hyp" || { echo cannot find hyp $hyp ; exit 1 ; }
test -f "$ref" || { echo cannot find ref $ref ; exit 1 ; }

tmpPrefix=/tmp/rjiw.$$
hypTmp=${tmpPrefix}.hyp
refTmp=${tmpPrefix}.ref

preprocessFile < $hyp > $hypTmp
preprocessFile < $ref > $refTmp

source ${PLG_GROUPS_STORAGE}/plggmeetween/envs/setup/jiwer.USE

exe=jiwer

info=$($exe $globalFlag -r $refTmp -h $hypTmp | awk '{printf "%.2f\n", $1*100}')
# manage errors
exitFlag=0
if test -z "$info"
then
  exitFlag=1
  echo '{"wer": "ERROR"}'
else
  exitFlag=0
  printf '{"wer": %s}\n' $info
fi

\rm -f ${tmpPrefix}.*

exit $exitFlag


