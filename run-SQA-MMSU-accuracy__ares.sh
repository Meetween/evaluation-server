#! /bin/bash

#SBATCH -A plgmeetween2026-cpu
#SBATCH -p plgrid
#SBATCH -N 1
#SBATCH --ntasks-per-node=1
#SBATCH --mem=1G
#SBATCH --job-name=sqaa
#SBATCH --time 00:10:00

# -----------
# manage args
# -----------

print_if_verbose() {
  if test $verbose -eq 1 ; then echo "$@" 1>&2 ; fi
}

show_help() {
  cat << EOF
ARGS: [-h] [-v] lang hypFile
  where
      -h        print help
      -v        verbose
      lang      two-digit language code
      hypFile   jsonl file with answer predictions
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
shift 2

test -f "$hyp" || { echo cannot find hyp $hyp ; exit 1 ; }

module load python/3.11.3-gcccore-12.3.0 &> /dev/null

exe=${PLG_GROUPS_STORAGE}/plggmeetween/envs/etc/MMSU/mmsu_evaluation__PLGRID.py

python $exe $debugInfo $hyp 

