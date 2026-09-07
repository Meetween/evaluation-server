#!/bin/bash

fixEmptyLines() {
  awk '{if(NF>0){print $0} else {print "EMPTY_LINE"}}'
}


if [ "$#" -ne 3 ]; then 
echo "ARGS: hypFile refFile segmentedOutHypFile"
exit
fi

hyp=$1
ref=$2
seg=$3

export SCRIPTDIR=$(cd $(dirname $0) ; pwd)/bin
normExe=$SCRIPTDIR/normalizeTextNIST.pl
segmenter=$SCRIPTDIR/mwerSegmenter
detok=$SCRIPTDIR/detokenizer.perl
tmpDir=$(mktemp -d)

## echo tmpDir $tmpDir 1>&2

tmptranslationfile=__translation
tmpmref=__mreference
tmpresegmentedfile=__segments
useCase=1

cat $ref | $normExe -c > $tmpDir/$tmpmref
cat $hyp | $normExe -c > $tmpDir/$tmptranslationfile

origDir=$(pwd)
cd $tmpDir

# segmentation s written on local file $tmpresegmentedfile
#
$segmenter -mref $tmpmref -hypfile $tmptranslationfile -usecase $useCase &> /dev/null

cd $origDir &> /dev/null

cat $tmpDir/$tmpresegmentedfile | $normExe -c | fixEmptyLines | $detok 2>/dev/null > $seg

\rm -rf $tmpDir

