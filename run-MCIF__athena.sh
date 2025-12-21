#! /bin/bash

#SBATCH -A plgmeetween2025-gpu-a100
#SBATCH -p plgrid-gpu-a100
#SBATCH -N 1
#SBATCH --ntasks-per-node=1
#SBATCH --gres=gpu:1
#SBATCH --mem=50G
#SBATCH --job-name=IF

# script for the evaluation of instruction following (IWSLT2025 shared task)


# -----------
# manage args
# -----------

show_help() {
  cat << EOF
ARGS: [-h] [-n] srcL tgtL hypFile refFile
  where
      -h	print help
      -n	do NOT perform re-segmentation of hypFile
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

test "$#" -ge 4 || { show_help ; exit 1 ; }
scrLang=$1
tgtLang=$2
hypFile=$3
refFile=$4
shift 4

test -f "$hypFile" || { echo cannot find hypFile $hypFile ; exit 1 ; }
test -f "$refFile" || { echo cannot find refFile $refFile ; exit 1 ; }

# source ENV
source ${PLG_GROUPS_STORAGE}/plggmeetween/envs/setup/mcif.USE

# the dir with the "mwerSegmenter" exe
export MWERSEGMENTER_ROOT=${PLG_GROUPS_STORAGE}/plggmeetween/envs/etc/mwerSegmenter/bin

# the evaluation script
exe=${PLG_GROUPS_STORAGE}/plggmeetween/envs/etc/MCIF/evaluation.py

track=short
if echo $refFile | grep -i 'LONG' &> /dev/null ; then track=long ; fi

python $exe -s $hypFile -r $refFile -t $track -l $tgtLang 2>/dev/null


