#! /usr/bin/env python

import sys
import torch
import librosa
import argparse
import statistics

from os import listdir
from os.path import isfile, join

parser = argparse.ArgumentParser()
parser.add_argument("wav_dir")
args = parser.parse_args()

wavDir = args.wav_dir
fileList = [obj for obj in listdir(wavDir) if isfile(join(wavDir, obj))]

predictor = torch.hub.load("tarepan/SpeechMOS:v1.2.0", "utmos22_strong", trust_repo=True).cuda()
scoreList = []
for f in fileList:
  audioF = join(wavDir, f)
  wave, sr = librosa.load(audioF, sr=None, mono=True)
  score = predictor(torch.from_numpy(wave).to("cuda").unsqueeze(0), sr)
  utmos = float(score[0])
  scoreList.append(utmos)
  ## print(f'utmos {f} {utmos}')

# compute mean and standard deviation

mean  = statistics.mean(scoreList)
stdev = statistics.pstdev(scoreList)

print(f'{mean} {stdev}')



