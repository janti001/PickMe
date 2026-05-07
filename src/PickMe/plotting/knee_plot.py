import seaborn as sns
from matplotlib.pyplot import subplots, savefig
import numpy as np
from ..utils import check_make_dir


def plot_knee(normalised_volume, index_threshold, norm_threshold, micrograph):
    """
    This function plots the volume-based filter so users can visualise the filter being imposed.

    :param normalised_volume: array of volumes which have been normalised against the max volume within the array, and be assorted in ascending order
    :param index_threshold: Integer value giving the index in which the objects should be retreieved
    :param norm_threshold: threshold value of the max normalised value 
    :type normalised_volume: numpy.ndarray
    :type threshold: int, np.int64

    :return: png file of figure 
    :rtype: tuple(fig, ax)
    """

    # --- Checking the correct data

    if isinstance(index_threshold, (str, float)):
        raise TypeError('Threshold must be an integer')
    if np.max(normalised_volume) > 1 or np.min(normalised_volume) <0:
        raise ValueError('Volume array must be normalised!')

    fig, ax = subplots(figsize=(5,5))
    #getting the x-axis ticks, which are the indices of the data
    index = np.arange(len(normalised_volume))

    knee_plot = sns.scatterplot(y=normalised_volume, x=index)
    #adding the diagonal
    knee_plot.axline(xy1=(0,0), xy2=(len(normalised_volume), 1), linestyle='-', color='red')
    #adding line for data
    knee_plot.plot(index, normalised_volume, color="#008080", alpha=0.8)
    #adding the vertical threshold line
    #ax.axvline(index_threshold, color='red', linestyle=(5, (10,3)), alpha=0.35, label='Threshold')
    knee_plot.axhline(norm_threshold, color='red', linestyle=(5, (10,3)), alpha=0.35)
    #adding labels
    knee_plot.set_title(f'Max-volume normalised volumes of {micrograph}')
    knee_plot.set_ylabel('NSR value w.r.t to the largest volume object') #NSR = N:Signal ratio intuition is, if the signal is much larger than noise, NSR = 0. Max-normalised volumes are essentially calculating this ratio
    knee_plot.set_xlabel('Index of the data')
    #adding labels for thresholds
    knee_plot.text(0, norm_threshold, f'{round(norm_threshold, 3)}',
    color='red',
    va='center', ha='right',
    transform=ax.get_yaxis_transform())

    #Make plotting directory if it has not been made yet
    output_directory = check_make_dir(job_name='plotting')
    # --- saving the figure
    #here we are assuming the user is using the same project structure
    #this can be changed
    knee_plot.get_figure().savefig(f'{output_directory}/{micrograph}_knee.png')

