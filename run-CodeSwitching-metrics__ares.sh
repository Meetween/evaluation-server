#! /bin/bash

#SBATCH -A plgmeetween2026-cpu
#SBATCH -p plgrid
#SBATCH -N 1
#SBATCH --ntasks-per-node=1
#SBATCH --mem=10G
#SBATCH --job-name=cse

# -----------
# manage args
# -----------

show_help() {
  cat << EOF
ARGS: [-h] [-v] srcLang tgtLang hypTsvFile refTsvFile
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
      args="$args"
      ;;
  esac
done

shift $((OPTIND-1))

[ "${1:-}" = "--" ] && shift


test "$#" -ge 4 || { show_help ; exit 1 ; }
src=$1
tgt=$2
hypTsv=$3
refTsv=$4
shift 4

test -f "$hypTsv" || { echo cannot find hypTsv $hypTsv ; exit 1 ; }
test -f "$refTsv" || { echo cannot find refTsv $refTsv ; exit 1 ; }

source ${PLG_GROUPS_STORAGE}/plggmeetween/envs/setup/pier.USE

exe=${PLG_GROUPS_STORAGE}/plggmeetween/envs/etc/Trustworthiness/do_pier_tsv.py

tmpF=/tmp/rcsM.$$.out

python $exe $args $src $tgt $hypTsv $refTsv &> $tmpF

if ! grep '"state":' < $tmpF
then
   echo '{"state": "ERROR", "reason": "unknown"}'
fi

\rm -f $tmpF

