#! /bin/bash

#SBATCH -A plgmeetween2026-cpu
#SBATCH -p plgrid
#SBATCH -N 1
#SBATCH --ntasks-per-node=1
#SBATCH --mem=10G
#SBATCH --time=00:30:00
#SBATCH --job-name=hSSUM


# -----------
# manage args
# -----------

show_help() {
  cat << EOF
ARGS: [-h] [-v] lang hypFile refFile
  where
      -h        print help
      -d        debug
      -b        use base model instead of large model
      lang      two-digit language code
      hypFile   json file with answer predictions
      refFile   json file with questtion-answer references
EOF
}


# A POSIX variable
OPTIND=1         # Reset in case getopts has been used previously in the shell.

# Initialize our own variables:
args=''
debugFlag=0

while getopts "hdb" opt; do
  case "$opt" in
    h)
      show_help
      exit 0
      ;;
    b)
      args="$args -b"
      ;;
    d)
      args="$args -d"
      debugFlag=1
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

source ${PLG_GROUPS_STORAGE}/plggmeetween/envs/setup/lettucedetect.USE

exe=${PLG_GROUPS_STORAGE}/plggmeetween/envs/etc/Trustworthiness/hallucinations_SSUM_eval.py

if test $debugFlag == 1
then
  python $exe $args $hyp $ref
else
  python $exe $args $hyp $ref 2>/dev/null
fi

