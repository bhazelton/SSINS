#!/bin/bash

#SBATCH --nodes=1
#SBATCH --ntasks=18
#SBATCH --time=01:00:00
#SBATCH --account=mwaeor
#SBATCH	--output=SSINS_%j.out
#SBATCH --error=SSINS_%j.err

module load singularity
export SINGULARITY_CACHEDIR=$MYGROUP/singularity_cache

#module use /group/mwa/software/modulefiles
#module load six
#module load pyuvdata
#module load h5py
#module load scipy
#module load matplotlib
#module load numpy
#module load pyyaml

data_dir=/astro/mwaeor/MWA/data

echo JOBID $SLURM_ARRAY_JOB_ID
echo TASKID $SLURM_ARRAY_TASK_ID
echo OBSID $obs

gpufiles=$(ls ${data_dir}/${obs}/*gpubox*.fits)

# Only do things if the outputs don't already exist
if [ ! -e ${outdir}/${obs}_SSINS_data.h5 ]; then

  echo "Executing python script for ${obs}"
  gpufiles=$(ls ${data_dir}/${obs}/*gpubox*.fits)
  metafile=$(ls ${data_dir}/${obs}/*.metafits)
  srun --export=all -n 1 --cpus-per-task 28 env - $(which singularity) exec $SINGULARITY_CACHEDIR/python_ssins-2020-02-13.sif /bin/bash -c "MWA_vis_to_SSINS.py -f $gpufiles $metafile -o $obs -d ${outdir}"
else
  echo "Output already exists. Skipping this obsid ${obs}."
fi
