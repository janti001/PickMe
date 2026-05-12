# PickMe 🎯
![alt text](https://github.com/janti001/PickMe/blob/main/assets/PickMe_logo.png)

<div>
A tool to incorporate into membrane segmentation-based workflows. Typical workflows involving membranes involve:

1. Membrane segmentation
2. Oversample the segmentation of desired objects to get particle picks
3. Clean up particle picks
4. Assign angles to particle picks
5. Export particles
6. Additional Processing to push resolution 

This tool looks to address the issue of parts 2 and 3 and provide some level of standardisation in this part of the workflow. This leads to individual groups writing custom scripts to address the needs of the individuals analysing the data - this leads to high levels of redundancy. 

This project look to reduce redundancy and aid in membrane oversampling, particle picking and other analysis and clean-up by being an open-source, easy-to-use and customisable tool.

# Disclaimer

I am very open to the contribution to this project by anyone interested. For additional tools/functionalities that you feel should be contributed/want to contribute, feel free to contact me (see .toml file for info).

## Additional Disclaimer
This is intended as a CLI tool use, however, there are some useful functions which could be used from this package in your own scripts.
<div>

# Installation Instructions

## Environment
- OS-independent
- Requires Python >= 3.14

## Dependencies
- numpy (2.4.3)
- pandas (3.0.1)
- matplotlib (3.10.8)
- starfile 
- mrcfile (1.5.4)
- napari (0.7.0)
- scikit-image (0.26.0)
- seaborn (0.13.2)
- tqdm (4.67.3)
- scipy (1.17.1)
## Install via git
As PickMe is being worked on daily, it is best to clone the github repository and then pip install it. This way, any updates to additional functionality, bug fixes etc. can be pushed to the repo, and all that needs to be done is to pull the github repository for the latest version.

This way, all changes will be visible without running 'pip install upgrade'

#### Make directory for the project
```
mkdir PickMe
cd PickMe
```

#### Create conda environment
```
conda create env -n PickMe python=3.14
conda activate PickMe
```

#### Pull the repo
When inside PickMe/
```
git init
git remote add origin https://github.com/janti001/PickMe.git
git pull origin/main
```

#### Pip install
```
pip install -e .
```
The "-e" will install an editable version, which is important as this project is being updated. So the code will update as and when you pull from the repo

## Via PIP
#### Make directory for project
```
mkdir PickMe
cd PickMe
```
#### Create Conda environment and Pip install
```
conda create env -n PickMe python=3.14
conda activate PickMe
pip install PickMe
```
<div>

# Usage
## Output handling
PickMe handles outputs by setting the default output root to ./outputs. Therefore, an output directory is made from wherever you run PickMe.

Ideally, you create a pickme project directory [Installation instructions](https://github.com/janti001/PickMe#make-directory-for-the-project) and run all the jobs you need to from within this directory to keep PickMe-related outputs organised.

## Pipeline
Collect tilt-series -> pre-process tilt-series -> get tomogram reconstructions -> run your favourite segmentation software -> **PickMe** -> Your favourite downstream particle processing pipeline (Warp/M/Relion, dynamo, imod etc.)

PickMe is supposed to be a highly modular tool which can be used in conjunction with other tools at yur disposal. For example: you can have a segmentation from Membrain-seg, filter or pick certain membranes using PickMe and then feed these data back to Membrain-seg to re-train.

Another example: PickMe can take a segmentation file, and oversample the membrane to geenrate particle picks with euler angles calculated, and this can be fed into the Warp/M/Relion pipeline.

-> This is where the power of PickMe comes from, being used in conjunction with other tools.

**Here we will assume you have segmentations that you want to take through the entire PickMe pipeline**:
At any point:
```
PickMe -h

PickMe [option] -h 
```
This will show the arguments and options you have - this is still 

<div>
### Extract and filter objects

  
First we need to filter the segmentations to get any suspsected noise that has been segmented.
```
PickMe extract_objects \
--input-dir path/to/directory/containing/segmentations
```
Here PickMe will write compressed mrc.gz and mrc.bz2 containing objects that have passed the filter and some diagnostic plots showing how the filter has been calculated.

<div>

### Choose objects
Second, you are able to visually choose objects using a wrapper that we have built for napari.
```
PickMe choose_objects \
--input-dir path/to/tomogram/reconstruction/.mrc/files
```

PickMe will find the latest extract job that has been run and use these segmentations.

When you run this job, a napari window will open with a RegionProps table on the right hand side.

Here you will see the tomogram and segmentaiton layers displayed in the napari console. Here you can show and unshow any pairs of tomograms and segmentations you please - selections of objects for a specific tomogram will only be applied once you have the segmentation highlighted in blue.

Once you have a tomogram/segmentation pair open, on the top right, from each drop down, click the respective names of the segmentation and tomogram layers you wish RegionProps to see.

In the right hand feature table, click labels and then "analyse", a feature table with the object labels will pop up at the bottom and some output in the command line should be printed to verify that PickMe can see the label table.

Click 'view when selected' option in the segmentation layer option in napari, and scroll through each object by clicking the object label in the label table displayed.

To select objects, simply **hold cmd/ctrl + Left-mouse click** on the object and it should be highlighted. This should be followed by dialogue in the command line which shows that the selection has been registered. Multiple objects can also be selected by **hold cmd/ctrl + left-mouse click** over multiple objects.

When you are ready to select objects from another tomogram/segmentatino pair, simpy select the segmentation layer of interest until it is highlighted blue and hide and unhide the appropriate layers and perform the same workflow as above.


When selections are completed, simply click off the napari window, and selections will be registered by PickMe and be written out as a mrc.gz / mrc.bz2 in ./outputs/choose_objects/jobxxx/


Optionally, users can input their own segmentations, or perhaps from another job and perform the workflow as above.
```
PickMe
- -input-dir path/to/tomogram/reconstruction/.mrc/files
--segmentation-dir path/to/segmentations
--input-job 23
```

<div>

### Particle extraction
Now we can extract particles from the surface of the objects that we have filtered and selected. This will create particles picked at the outersurface of these objects, calculate euler angles to orient the particles normal to the membrane and write all of the particles into a star file - both across all tomograms processed (particles.star) or a per tomogram particle star file (TS_xyxy_particles.star).

```
PickMe particle_extract \
--sample-rate 5
--cmm

```

Optionally, users can input a segmetation file(s) they would like to use, or a certain job number - as for a choose_objects job.




# Potential new features coming
**Different filter algorithms/types**
- Implement an otsu-threshold based filter on log-transformed volumes
- ML/DL classifier using a feature set of the objects

**Particle coordinate manipulation**
- Adding particle coordinate offset so TM proteins can be picked

**Alternate file type outputs for particle coordinates**
- Potentially writing wrappers which can handle the conversion of star files to file types that other software use such as .motl





