import seaborn as sns 
from matplotlib.pyplot import subplots
from pathlib import Path
from ..utils import check_make_dir


def plot_angles(star_data, output_dir, tomogram_name=None):
    '''
    Plots the distribution of the euler angles across all of the tomograms processed, to check if there are any biases in the distribution of angles which may affect downstream processing and alignment.
    
    Rot should have a uniform distribution, while tilt and psi may have some bias depending on the shape of the membrane and the sampling, but we want to check if there are any extreme biases which may affect downstream processing.
    
    :param star_data: the star dataframe containing the euler angles and other data for each particle
    :param output_dir: directory win which the output of the job it is being called in. I.e., If it is being called in Job001 (which particle_extract) - this should be supplied.
    :param tomogram_name: name of the tomogram file that is being processed. 
    :return: a plot of the distribution of the euler angles
    '''
    colors= sns.color_palette('viridis')
    fig, ax = subplots(ncols=3, figsize=(15,6))
    sns.histplot(ax = ax[0], data=star_data['rlnAngleTilt'], alpha=0.5, color=colors[0], kde=True, bins=100)
    #sns.kdeplot(ax=ax[0], data=per_tomo_data_df['rlnAngleTilt'], color='black')
    sns.histplot(ax = ax[1], data=star_data['rlnAngleRot'], alpha=0.5, color=colors[1], kde=True, bins=100)
    sns.histplot(ax = ax[2], data=star_data['rlnAnglePsi'], alpha=0.5, color=colors[2], kde=True, bins=100)
    sns.set_style('whitegrid')
    sns.set_context("notebook")
    ax[0].set_xlabel('Theta (degrees)');
    ax[1].set_xlabel('Rot (degrees)');
    ax[2].set_xlabel('Azimuthal (degrees)');
    ax[0].set_title('Distribution of Theta Angles');
    ax[1].set_title('Distribution of Rot Angles');
    ax[2].set_title('Distribution of Azimuthal Angles');

    #make plotting directory if it has not been made yet
    output_directory = Path(output_dir) / 'AnglePlots'
    output_directory.mkdir(exist_ok=True)
    if tomogram_name is not None:
        fig.savefig(f'{output_directory}/{tomogram_name}.png', format='png')
    else:
        fig.savefig(f'{output_directory}/Angles_distribution.png', format='png')