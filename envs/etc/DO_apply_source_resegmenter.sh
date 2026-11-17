#!/bin/bash

if [ "$#" -ne 3 ]; then 
echo "ARGS: hypFile refFile segmentedOutHypFile"
exit
fi

hyp=$1
ref=$2
seg=$3

lang=en
exe=${PLG_GROUPS_STORAGE}/plggmeetween/evaluation/DO_source_resegmenter.sh

bash $exe $lang $hyp $ref > $seg

