#! /bin/bash


resegment_hyp_file() {
  hypIn=$1
  refIn=$2
  lang=$3

  resExe=${PLG_GROUPS_STORAGE}/plggmeetween/envs/etc/mwerSegmenter/DO_apply_mwerSegmenter.sh
  segChars=${PLG_GROUPS_STORAGE}/plggmeetween/envs/etc/segment_chars.py
  unsChars=${PLG_GROUPS_STORAGE}/plggmeetween/envs/etc/unsegment_chars.py

  tmpDir=$(mktemp -d)
  tmpBufHyp=${tmpDir}/buf.hyp
  tmpBufRef=${tmpDir}/buf.ref
  tmpBufOut=${tmpDir}/buf.out

  charLevelFlag=0
  case $lang in
    zh|ja|ko)
      charLevelFlag=1
      ;;
  esac

  if test $charLevelFlag != 1
  then
    # remove special chars (Jan code)
    cat $hypIn \
      | sed -e "s/&apos;/'/g" -e 's/&#124;/|/g' -e "s/&amp;/&/g" -e 's/&lt;//g' -e 's/&gt;//g' -e 's/&quot;/"/g' -e 's/&#91;/[/g' -e 's/&#93;/]/g' -e "s/>//g" -e "s/<//g" -e 's/#//g' \
      > $tmpBufHyp

    cat $refIn \
      | sed -e "s/&apos;/'/g" -e 's/&#124;/|/g' -e "s/&amp;/&/g" -e 's/&lt;//g' -e 's/&gt;//g' -e 's/&quot;/"/g' -e 's/&#91;/[/g' -e 's/&#93;/]/g' -e "s/>//g" -e "s/<//g" -e 's/#//g' \
      > $tmpBufRef

    $resExe $tmpBufHyp $tmpBufRef $tmpBufOut
    cat $tmpBufOut

  else
    # remove special chars (Jan code) and segment in individual chars
    cat $hypIn \
      | sed -e "s/&apos;/'/g" -e 's/&#124;/|/g' -e "s/&amp;/&/g" -e 's/&lt;//g' -e 's/&gt;//g' -e 's/&quot;/"/g' -e 's/&#91;/[/g' -e 's/&#93;/]/g' -e "s/>//g" -e "s/<//g" -e 's/#//g' \
      | python3 ${segChars} \
      > $tmpBufHyp

    cat $refIn \
      | sed -e "s/&apos;/'/g" -e 's/&#124;/|/g' -e "s/&amp;/&/g" -e 's/&lt;//g' -e 's/&gt;//g' -e 's/&quot;/"/g' -e 's/&#91;/[/g' -e 's/&#93;/]/g' -e "s/>//g" -e "s/<//g" -e 's/#//g' \
      | python3 ${segChars} \
      > $tmpBufRef

    $resExe $tmpBufHyp $tmpBufRef $tmpBufOut

    # remove previously introduced spaces
    cat $tmpBufOut | python3 ${unsChars}

  fi

  \rm -rf $tmpDir
}

print_help() {
  cat << EOF
ARGS: lang hypFile refFile
  print on STDOUT the \$hypFile realigned with the \$refFile using the MWER-segmenter
EOF
}


test "$#" -ge 3 || { print_help  ; exit 1 ; }
lang=$1
hypFile=$2
refFile=$3
shift 3

resegment_hyp_file $hypFile $refFile $lang


