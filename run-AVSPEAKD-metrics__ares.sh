#! /bin/bash

#SBATCH -A plgmeetween2026-cpu
#SBATCH -p plgrid
#SBATCH -N 1
#SBATCH --ntasks-per-node=1
#SBATCH --mem=10G
#SBATCH --job-name=ram

# -----------
# manage args
# -----------

show_help() {
  cat << EOF
ARGS: [-h] [-v] lang hypTsvFile refTsvFile
  where
      -h        print help
      -v        verbose
EOF
}


# A POSIX variable
OPTIND=1         # Reset in case getopts has been used previously in the shell.

# Initialize our own variables:
args=''

while getopts "hv" opt; do
  case "$opt" in
    h)
      show_help
      exit 0
      ;;
    v)
      args="$args -d"
      ;;
  esac
done

shift $((OPTIND-1))

[ "${1:-}" = "--" ] && shift


test "$#" -ge 3 || { show_help ; exit 1 ; }
lang=$1
hypTsv=$2
refTsv=$3
shift 3

test -f "$hypTsv" || { echo cannot find hypTsv $hypTsv ; exit 1 ; }
test -f "$refTsv" || { echo cannot find refTsv $refTsv ; exit 1 ; }

# source ENV
source ${PLG_GROUPS_STORAGE}/plggmeetween/envs/setup/evaluate.USE

# the evaluation script
exe=${PLG_GROUPS_STORAGE}/plggmeetween/envs/etc/AVSPEAKD/eval_AVSPKD_testset.py

python $exe $args $hypTsv $refTsv




