#! /bin/bash

#SBATCH -A plgmeetween2004-cpu
#SBATCH -p plgrid
#SBATCH -N 1
#SBATCH --ntasks-per-node=1
#SBATCH --mem=10G
#SBATCH --job-name=Def

# -----------
# manage args
# -----------

print_error() {
  echo "ERROR: $@" 1>&2
}

print_if_verbose() {
  if test $verbose -eq 1 ; then echo "$@" 1>&2 ; fi
}

show_help() {
  cat << EOF 1>&2
ARGS: [-h] [-v] [-d] task testset organization modelname modelsize modeldescription other+ 
  where
      -h        	print help
      -v        	verbose
      -d        	debug
      task      	ASR|MT|ST|LIPREAD
      testset   	MUSTC|FLORES|ACL6060|LRS3|MTEDX|... (depends on task)
      organization 	TLT|FBK|KIT|ITU|TAUS|ZOOM|PI|CYF
      modelname		a string without-spaces (e.g. Seamless-m4t-v2-large)
      modelsize 	a string without-spaces (e.g. 2.3B-parameters)
      modeldescription 	a quoted string (e.g. "foundational all-in-one Multilingual and Multimodal Machine Translation model by Meta AI, delivering translation for speech and text in nearly 100 languages")
      other+            depends on task:
			   lang hypFile       (if task == ASR|LIPREAD)
			   srcL tgtL hypFile  (if task == MT|ST)
EOF
}


check_task() {
  task=$1
  case $task in
    ASR|MT|ST|LIPREAD)
      ;;
    *)
      print_error unknown task $task
      show_help
      exit 1
      ;;
  esac
}

check_testset() {
  testset=$1
  task=$2
  case $task in
    ASR)
      case $testset in
        MUSTC|LRS3|ACL6060|MTEDX)
          ;;
        *)
          print_error unknown testset $testset for task $task 
          show_help ; exit 1
          ;;
        esac
      ;;
    MT)
      case $testset in
        FLORES|ACL6060)
          ;;
        *)
          print_error unknown testset $testset for task $task
          show_help ; exit 1
          ;;
        esac
      ;;
    ST)
      case $testset in
        MUSTC|ACL6060)
          ;;
        *)
          print_error unknown testset $testset for task $task
          show_help ; exit 1
          ;;
        esac

      ;;
    LIPREAD)
      case $testset in
        LRS3)
          ;;
        *)
          print_error unknown testset $testset for task $task
          show_help ; exit 1
          ;;
        esac
      ;;
  esac
}

check_organization() {
  organization=$1
  case $organization in
    TLT|FBK|KIT|ITU|TAUS|ZOOM|PI|CYF)
      ;;
    *)
      print_error unknown organization $organization
      show_help
      exit 1
      ;;
  esac
}


# A POSIX variable
OPTIND=1         # Reset in case getopts has been used previously in the shell.

# Initialize our own variables:
verbose=0
debug=0

while getopts "dhv" opt; do
  case "$opt" in
    h)
      show_help
      exit 0
      ;;
    d)
      debug=1
      ;;
    v)
      verbose=1
      ;;
  esac
done

shift $((OPTIND-1))

[ "${1:-}" = "--" ] && shift

test $# -ge 8 || { echo ERROR: missing args 1>&2 ; show_help ; exit 1 ; }

task=$1
testset=$2
organization=$3
modelname=$4
modelsize=$5
modeldescription=$6
shift 6

cat <<EOF
task $task
testset $testset
organization $organization
modelname $modelname
modelsize $modelsize
modeldescription $modeldescription
$@
EOF

check_task $task
check_testset $testset $task
check_organization $organization

# process the remaining args

# this script dir
scriptDir=${PLG_GROUPS_STORAGE}/plggmeetween/evaluation
# the dir to write the output json string
outDir=${scriptDir}/sessions

# jj is the script to join json files
jj=${scriptDir}/../envs/etc/jj.py

tmpPrefix=/tmp/Defa.$$

# flags to perform sacrebleu scores
doSB=1
realignFlag='-n'
case $task in 
  ASR|LIPREAD)
    sl=$1
    hypFile=$2
    shift 2
    refDir=${scriptDir}/../tasks/${task}/${testset}/${sl}
    case $testset in
      LRS3)
        # special case of LRS3:
	#   both hyp and ref are tsv files with lines with format
	#   $videoid TAB $sentence
	refFileTsv=${refDir}/*.${sl}.tsv.sorted
	refFileTmp=${tmpPrefix}.sorted.ref
	cut -f2 $refFileTsv > $refFileTmp
	refFile=$refFileTmp
	hypFileTmp=${tmpPrefix}.sorted.hyp
	sort $hypFile | cut -f2 > $hypFileTmp
	hypFile=$hypFileTmp
      ;;
      *)
        refFile=${refDir}/*.${sl}
      ;;
    esac
    # do not performe sacrebleu (only WER)
    doSB=0
    tl=none
    subtask=none
    ;;
  MT|ST)
    sl=$1
    tl=$2
    hypFile=$3
    shift 3
    langPair=${sl}-${tl}
    refDir=${scriptDir}/../tasks/${task}/${testset}/${langPair}
    refFile=${refDir}/*.${langPair}.${tl}
    subtask=$langPair
    ;;
esac


test -f "$hypFile" || { print_error cannot find hypFile $hypFile ; exit 1 ; }
## test -f "$refFile" || { print_error cannot find refFile $refFile ; exit 1 ; }


tmpSWER=${tmpPrefix}.scores.WER
tmpSSB=${tmpPrefix}.scores.SB
tmpSALL=${tmpPrefix}.scores.ALL
tmpMeta=${tmpPrefix}.meta
tmpFinal=${tmpPrefix}.final

# run WER if needed
bash ${scriptDir}/run-wer__ares.sh $sl $hypFile $refFile > ${tmpSWER}
# manage failure
test $? -eq 0 || echo '{"wer": "ERROR"}' > ${tmpSWER}


# run SACREBLEU if needed
if test $doSB -eq 1
then
  bash ${scriptDir}/run-sacrebleu__ares.sh $realignFlag $sl $tl $hypFile $refFile > ${tmpSSB}
  # manage failure
  test $? -eq 0 || echo '{"bleu": "ERROR", "chrf": "ERROR", "ter": "ERROR"}' > ${tmpSSB}
  #
  echo '{"scores": '$($jj ${tmpSWER} ${tmpSSB})'}' > ${tmpSALL}
else
  echo '{"scores": '$(cat ${tmpSWER})'}' > ${tmpSALL}
fi

date=$(date +'%Y%m%dT%H%M%S')
cat << EOF > $tmpMeta
{
    "task": "$task",     
    "testset": "$testset",
    "source-language": "$sl",
    "target-language": "$tl",
    "subtask": "$langPair",
    "user": "$USER",
    "organization": "$organization",
    "model-name": "$modelname",
    "model-size": "$modelsize",
    "model-description": "$modeldescription",
    "date": "$date"
}
EOF

## jq -s 'add' $tmpMeta $tmpSALL > $tmpFinal
$jj $tmpMeta $tmpSALL > $tmpFinal

echo evaluation results:
cat $tmpFinal

outJson=${outDir}/${organization}_${date}.json
cat $tmpFinal > $outJson

# check the return status and print final report
if test $? -eq 0
then
  echo successfully written evaluation file $outJson
else
  echo ERROR: problems in writing evaluation file $outJson
fi


if ! test $debug -eq 1
then
  \rm -f ${tmpPrefix}.*
fi

