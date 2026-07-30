#! /bin/bash

#SBATCH -A plgmeetween2026-gpu-a100
#SBATCH -p plgrid-gpu-a100
#SBATCH -N 1
#SBATCH --ntasks-per-node=1
#SBATCH --gres=gpu:1
#SBATCH --mem=50G
#SBATCH --job-name=ACHAP

# script for the evaluation the ACHAP task 


# -----------
# manage args
# -----------

show_help() {
  cat << EOF
ARGS: [-h] srcL tgtL hypFile refFile
  where
      -h	print help
EOF
}


# A POSIX variable
OPTIND=1         # Reset in case getopts has been used previously in the shell.

# Initialize our own variables:
debugFlag=0

while getopts "hd" opt; do
  case "$opt" in
    h)
      show_help
      exit 0
      ;;
    d)
      debugFlag=1
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

# source the proper env
source ${PLG_GROUPS_STORAGE}/plggmeetween/envs/setup/ifeval26.USE

# set with the path of the dir with the "DO_apply_mwerSegmenter.sh" 
export MWERSEGMENTER_ROOT=${PLG_GROUPS_STORAGE}/plggmeetween/envs/etc/mwerSegmenter

# define the exe to be invoked
exe=${PLG_GROUPS_STORAGE}/plggmeetween/envs/etc/ACHAP/achap_standalone_eval.py


if test ${debugFlag} == 1
then
  python $exe -s $hypFile -r $refFile -l $tgtLang
else 
  python $exe -s $hypFile -r $refFile -l $tgtLang 2>/dev/null
fi

