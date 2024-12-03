#! /bin/bash

#SBATCH -A plgmeetween2004-gpu-a100
#SBATCH -p plgrid-gpu-a100
#SBATCH -N 1
#SBATCH --ntasks-per-node=1
#SBATCH --gres=gpu:1
#SBATCH --mem=10G
#SBATCH --job-name=um


source ${PLG_GROUPS_STORAGE}/plggmeetween/envs/setup/speechmos.USE

exe=${PLG_GROUPS_STORAGE}/plggmeetween/envs/etc/UTMOS/compute_utmos_from_dir.py

python $exe "$@" 2>/dev/null

