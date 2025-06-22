#! /bin/bash

#SBATCH -A plgmeetween2025-cpu
#SBATCH -p plgrid
#SBATCH -N 1
#SBATCH --ntasks-per-node=1
#SBATCH --mem=10G
#SBATCH --job-name=rtw

# -----------
# manage args
# -----------

show_help() {
  cat << EOF
ARGS: [-g] [-h] [-v] lang hypTsvFile refTsvFile
  where
      -g        apply a global minimal alignment between reference and hypothesis sentences before computing the WER
      -h        print help
      -v        verbose
EOF
}


# A POSIX variable
OPTIND=1         # Reset in case getopts has been used previously in the shell.

# Initialize our own variables:
args=''

while getopts "ghv" opt; do
  case "$opt" in
    g)
      args="$args -g"
      ;;
    h)
      show_help
      exit 0
      ;;
    v)
      args="$args -v"
      ;;
  esac
done

shift $((OPTIND-1))

[ "${1:-}" = "--" ] && shift


# this script dir
scriptDir=${PLG_GROUPS_STORAGE}/plggmeetween/evaluation

sl=$1
hypTsv=$2
refTsv=$3
shift 3

tmpPrefix=/tmp/rtw.$$


refTmp=${tmpPrefix}.sorted.ref
sort $refTsv | cut -f2 > $refTmp
hypTmp=${tmpPrefix}.sorted.hyp
sort $hypTsv | cut -f2 > $hypTmp


bash ${scriptDir}/run-wer__ares.sh $args $sl $hypTmp $refTmp 

\rm -f $hypTmp $refTmp

