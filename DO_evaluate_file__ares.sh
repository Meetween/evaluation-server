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
      task      	ASR|MT|ST|LIPREAD|SQA|SUM|SSUM
      testset   	MUSTC|FLORES|ACL6060|LRS3|MTEDX|DIPCO|SPOKENSQUAD|ICSI|AUTOMIN... (depends on task)
      organization 	TLT|FBK|KIT|ITU|TAUS|ZOOM|PI|CYF
      modelname		a string without-spaces (e.g. Seamless-m4t-v2-large)
      modelsize 	a string without-spaces (e.g. 2.3B-parameters)
      modeldescription 	a quoted string (e.g. "foundational all-in-one Multilingual and Multimodal Machine Translation model by Meta AI, delivering translation for speech and text in nearly 100 languages")
      other+            depends on task:
			   lang hypFile       (if task == ASR|LIPREAD|SQA|SUM|SSUM)
			   srcL tgtL hypFile  (if task == MT|ST)
  Notes:
      1) the format of hypFile depends on the task/testset:
           - jsonl with summarization hypotheses   if task is SUM or SSUM
           - json with predictions                 if testset is SQA/SPOKENSQUAD
      	   - videoId TAB sentence (one for line)   if testset == LRS3
	     (an example of videoId is the string  "test/0Fi83BHQsMA/00002")
	   - sentence (one for line)               in all the other tasks
      2) for the DIPCO testset currently only the "close-talk" subset is supported
         (the "far-field" is not supported). hypFile must be a a 3405 lines file
         with transcriptions of the close-talk audios.
EOF
}


check_task() {
  task=$1
  case $task in
    ASR|MT|ST|LIPREAD|SQA|SUM|SSUM)
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
        MUSTC|LRS3|ACL6060|MTEDX|DIPCO)
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
        MUSTC|ACL6060|MTEDX)
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
    SQA)
      case $testset in
        SPOKENSQUAD)
          ;;
        *)
          print_error unknown testset $testset for task $task
          show_help ; exit 1
          ;;
      esac
      ;;
    SUM)
      case $testset in
        ICSI|AUTOMIN)
          ;;
        *)
          print_error unknown testset $testset for task $task
          show_help ; exit 1
          ;;
      esac
      ;;
    SSUM)
      case $testset in
        ICSI)
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

# the script to join json files
joinJson=${scriptDir}/../envs/etc/jj.py

tmpPrefix=/tmp/Defa.$$

# flags to perform WER, SA(sacrebleu), SQA(SQA Accuracy), ROU(SUM-rouge) scores
doWER=1
doSB=1
doSQA=0
doROU=0
realignFlag='-n'
globalFlag='-g'
case $task in 
  ASR|LIPREAD)
    sl=$1
    hypFile=$2
    shift 2
    refDir=${scriptDir}/../tasks/${task}/${testset}/${sl}
    case $testset in
      DIPCO)
        # special case of DIPCO:
	#   currently only the "close-talk" subset is supported
	#   (the "far-field" is not supported).
	#   hyp must be a 3405 lines file with transcriptions of
	#   the close-talk audios
	#
        refFile=${refDir}/close-talk.${sl}
      ;;
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
  SQA)
    sl=$1
    hypFile=$2
    shift 2
    refDir=${scriptDir}/../tasks/${task}/${testset}/${sl}
    refFile=${refDir}/*.${sl}.json
    doWER=0
    doSB=0
    doSQA=1
    ;;
  SUM|SSUM)
    sl=$1
    hypFile=$2
    shift 2
    refDir=${scriptDir}/../tasks/${task}/${testset}/${sl}
    refFile=${refDir}/*.${sl}.ref.jsonl
    doWER=0
    doSB=0
    doROU=1
    ;;
esac


test -f "$hypFile" || { print_error cannot find hypFile $hypFile ; exit 1 ; }
## test -f "$refFile" || { print_error cannot find refFile $refFile ; exit 1 ; }


# the json with a single score only
tmpSWER=${tmpPrefix}.scores.WER
tmpSSB=${tmpPrefix}.scores.SB
tmpSSQA=${tmpPrefix}.scores.SQA
tmpSROU=${tmpPrefix}.scores.ROU
#
# the json with all the scores joned (if needed)
tmpSALL=${tmpPrefix}.scores.ALL
#
# the json with the meta data only
tmpMeta=${tmpPrefix}.meta
#
# the final json with all the info (meta + all scores)
tmpFinal=${tmpPrefix}.final

# run WER if needed
if test $doWER -eq 1
then
  bash ${scriptDir}/run-wer__ares.sh $globalFlag $sl $hypFile $refFile > ${tmpSWER}
  # manage failure
  test $? -eq 0 || echo '{"wer": "ERROR"}' > ${tmpSWER}
fi

# run SACREBLEU if needed
if test $doSB -eq 1
then
  bash ${scriptDir}/run-sacrebleu__ares.sh $realignFlag $sl $tl $hypFile $refFile > ${tmpSSB}
  # manage failure
  test $? -eq 0 || echo '{"bleu": "ERROR", "chrf": "ERROR", "ter": "ERROR"}' > ${tmpSSB}
fi

# run SQA if needed
if test $doSQA -eq 1
then
  bash ${scriptDir}/run-SQA-accuracy__ares.sh $sl $hypFile $refFile > ${tmpSSQA}
  # manage failure
  test $? -eq 0 || echo '{"accuracy": "ERROR"}' > ${tmpSSQA}
fi

# run ROU if needed
if test $doROU -eq 1
then
  bash ${scriptDir}/run-SUM-rouge__ares.sh $sl $hypFile $refFile > ${tmpSROU}
  # manage failure
  test $? -eq 0 || echo '{"R-1": "ERROR", "R-2": "ERROR", "R-L": "ERROR"}' > ${tmpSROU}
fi


# join all the single json score files
jFList=""
for f in ${tmpSWER} ${tmpSSB} ${tmpSSQA} ${tmpSROU}
do
  if test -f $f ; then jFList="$jFList $f" ; fi
done
echo '{"scores": '$($joinJson ${jFList})'}' > ${tmpSALL}



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

$joinJson $tmpMeta $tmpSALL > $tmpFinal

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

