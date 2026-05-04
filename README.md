# PickMe
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

I am very open to the contribution to this project by anyone interested. For additional tools/functionalities that you feel should be contributed/want to contribute, feel free to contact me.
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

```
conda create env -n PickMe python=3.14
conda activate PickMe
pip install PickMe
```
<div>

# Usage
Will be added soon. To-be-updated



