#! /bin/bash

#SBATCH -A plgmeetween2026-gpu-a100
#SBATCH -p plgrid-gpu-a100
#SBATCH -N 1
#SBATCH --ntasks-per-node=1
#SBATCH --gres=gpu:1
#SBATCH --mem=50G
#SBATCH --job-name=IF26

# script for the evaluation of the IWSLT-2026 Instruction Following task


tmpPrefix=/tmp/rI26.$$

# ---------
# functions
# ---------

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

# source the proper env
source ${PLG_GROUPS_STORAGE}/plggmeetween/envs/setup/ifeval26.USE

# set with the path of the dir with the "DO_apply_mwerSegmenter.sh" 
export MWERSEGMENTER_ROOT=${PLG_GROUPS_STORAGE}/plggmeetween/envs/etc/mwerSegmenter

# define the exe to be invoked
exe=mcif_eval


track=short
if cat $refFile | grep -i '<task' | grep -i 'track="long"' &>/dev/null  ; then track=long ; fi

tmpOut=${tmpPrefix}.out
tmpErr=${tmpPrefix}.err
$exe -s $hypFile -r $refFile -t $track -l $tgtLang 1> $tmpOut 2> $tmpErr

# check if the computation has been successfull
if grep -P '"state":\s+"OK"' < $tmpOut &> /dev/null
then
  cat $tmpOut
else
  state="ERROR"
  echo tmpErr START 1>&2
  cat $tmpErr 1>&2
  echo tmpErr END 1>&2
  if grep -P '^Exception:' < $tmpErr &> /dev/null
  then
    reason=$(grep -P '^Exception:' < $tmpErr | perl -pe 's|^Exception: ||')
  else
    reason="INTERNAL_ERROR"
  fi
  printf '{"state": "%s", "reason": "%s"}\n' "$state" "$reason"
fi

\rm -f $tmpOut $tmpErr

