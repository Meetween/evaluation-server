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
ARGS: [-h] [-v] language hypJsonFile refJsonFile
  where
      -h	print help
      -v	verbose
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
      args='-v'
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


# the script to extract pure text from json hyp and ref
exe1=${PLG_GROUPS_STORAGE}/plggmeetween/envs/etc/SQA/extract_aligned_text.py

tmpDir=$(mktemp -d)
tmpTxtHyp=${tmpDir}/hyp.txt
tmpTxtRef=${tmpDir}/ref.txt

# the low level evaluation script using only text files
exe2=${PLG_GROUPS_STORAGE}/plggmeetween/evaluation/run-bert__athena.sh

# extract the text files
python3 $exe1 $hypFile $refFile $tmpTxtHyp $tmpTxtRef

# evaluate the text files
bash $exe2 $args $language $tmpTxtHyp $tmpTxtRef

\rm -rf $tmpDir

