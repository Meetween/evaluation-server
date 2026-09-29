#! /bin/bash

#SBATCH -A plgmeetween2026-gpu-a100
#SBATCH -p plgrid-gpu-a100
#SBATCH -N 1
#SBATCH --ntasks-per-node=1
#SBATCH --gres=gpu:1
#SBATCH --mem=10G
#SBATCH --job-name=bert


# -----------
# manage args
# -----------

show_help() {
  cat << EOF
ARGS: [-h] [-v] language hypFile refFile
  where
      -h	print help
      -v	verbose
EOF
}


# A POSIX variable
OPTIND=1         # Reset in case getopts has been used previously in the shell.

# Initialize our own variables:
debugFlag=''

while getopts "hv" opt; do
  case "$opt" in
    h)
      show_help
      exit 0
      ;;
    v)
      debugFlag='-d'
      ;;
  esac
done

shift $((OPTIND-1))

[ "${1:-}" = "--" ] && shift

test "$#" -ge 3 || { show_help ; exit 1 ; }
language=$1
hypFile=$2
refFile=$3
shift 3

test -f "$hypFile" || { echo cannot find hypFile $hypFile ; exit 1 ; }
test -f "$refFile" || { echo cannot find refFile $refFile ; exit 1 ; }

# source ENV
source ${PLG_GROUPS_STORAGE}/plggmeetween/envs/setup/bert.USE

# the evaluation script
exe=${PLG_GROUPS_STORAGE}/plggmeetween/envs/etc/bert/bertscore.py

python $exe $debugFlag -l $language $hypFile $refFile 2>/dev/null


