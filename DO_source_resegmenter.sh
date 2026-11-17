#! /bin/bash


dump_original_files() {
  hyp=$1
  ref=$2
  lang=$3
  oDir=${PLG_GROUPS_STORAGE}/plggmeetween/IWSLT26/segmented_submissions
  cat $hyp > ${oDir}/${SLURM_JOB_ID}_${$}_hyp
  cat $ref > ${oDir}/${SLURM_JOB_ID}_${$}_ref
  echo $lang > ${oDir}/${SLURM_JOB_ID}_${$}_lang
}

check_save_segmented_hyp_file() {
  segmHyp=$1
  if test "${TASK:-empty}" != empty \
     -a "${TEST_SET:-empty}" != empty \
     -a "${SOURCE_LANGUAGE:-empty}" != empty \
     -a "${TARGET_LANGUAGE:-empty}" != empty \
     -a "${USER_ID:-empty}" != empty \
     -a "${MODEL:-empty}" != empty
  then
    fName=$(echo segm.${USER_ID}.${MODEL}.${TASK}.${TEST_SET}.${SOURCE_LANGUAGE}.${TARGET_LANGUAGE}.${SLURM_JOB_ID}.${$} \
      | perl -pe 's/ /_/g')
    fPath=${PLG_GROUPS_STORAGE}/plggmeetween/IWSLT26/segmented_submissions/${fName}
    cat ${segmHyp} > $fPath
  fi
}

remove_empty_lines() {
  awk '{if(NF>0){print $0}}'
}

remove_special_chars() {
  sed -e "s/&apos;/'/g" -e 's/&#124;/|/g' -e "s/&amp;/&/g" -e 's/&lt;//g' -e 's/&gt;//g' -e 's/&quot;/"/g' -e 's/&#91;/[/g' -e 's/&#93;/]/g' -e "s/>//g" -e "s/<//g" -e 's/#//g'
}

resegment_hyp_file() {
  hypIn=$1
  refIn=$2
  lang=$3

  source ${PLG_GROUPS_STORAGE}/plggmeetween/envs/setup/source_resegmenter.USE
  exe=source_resegmenter

  segChars=${PLG_GROUPS_STORAGE}/plggmeetween/envs/etc/segment_chars.py
  unsChars=${PLG_GROUPS_STORAGE}/plggmeetween/envs/etc/unsegment_chars.py

  tmpDir=$(mktemp -d)
  tmpBufHyp=${tmpDir}/buf.hyp
  tmpBufRef=${tmpDir}/buf.ref
  tmpBufOut=${tmpDir}/buf.out
  tmpBufOut2=${tmpDir}/buf.out2

  charLevelFlag=0
  case $lang in
    zh|ja|ko)
      charLevelFlag=1
      ;;
  esac

  if test $charLevelFlag != 1
  then
    # remove empty lines and special chars (Jan code)
    cat $hypIn | remove_empty_lines | remove_special_chars > $tmpBufHyp
    cat $refIn | remove_empty_lines | remove_special_chars > $tmpBufRef

    $exe --segmenter xlr-labse --source-texts $tmpBufHyp --reference-texts $tmpBufRef --backtranslation-texts $tmpBufRef --output $tmpBufOut
    cat $tmpBufOut
    # save segmented hyp if needed
    check_save_segmented_hyp_file $tmpBufOut

  else
    # remove empty lines and special chars (Jan code) and segment in individual chars
    cat $hypIn | remove_empty_lines | remove_special_chars \
      | python3 ${segChars} > $tmpBufHyp

    cat $refIn | remove_empty_lines | remove_special_chars \
      | python3 ${segChars} > $tmpBufRef

    $exe --segmenter xlr-labse --source-texts $tmpBufHyp --reference-texts $tmpBufRef --backtranslation-texts $tmpBufRef --output $tmpBufOut

    # remove previously introduced spaces
    cat $tmpBufOut | python3 ${unsChars} > $tmpBufOut2
    cat $tmpBufOut2
    # save segmented hyp if needed
    check_save_segmented_hyp_file $tmpBufOut2

  fi

  \rm -rf $tmpDir
}

print_help() {
  cat << EOF
ARGS: lang hypFile refFile
  print on STDOUT the \$hypFile realigned with the \$refFile using the source_resegmenter
EOF
}


test "$#" -ge 3 || { print_help  ; exit 1 ; }
lang=$1
hypFile=$2
refFile=$3
shift 3

## dump_original_files $hypFile $refFile $lang
resegment_hyp_file $hypFile $refFile $lang


