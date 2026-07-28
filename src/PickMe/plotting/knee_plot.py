import seaborn as sns
from matplotlib.pyplot import close, subplots
import numpy as np
from pathlib import Path


def plot_knee(normalised_volume, index_threshold, norm_threshold, micrograph, output_dir):
    """Save a diagnostic scatter plot of the volume-based knee filter.

    Plots each object's max-normalised volume against its sorted index,
    overlaid with the reference diagonal used to find the knee and a
    horizontal line marking the detected threshold, so the filtering
    decision made by `PickMe.filter.knee_detection` can be inspected
    visually. Writes the figure to
    ``<output_dir>/plots/<micrograph>_knee.png`` (the ``plots``
    subdirectory is created if it does not already exist) and does not
    return anything.

    Args:
        normalised_volume (numpy.ndarray): Object volumes normalised
            against the largest volume in the set (values in [0, 1]),
            sorted ascending.
        index_threshold (int): Index into ``normalised_volume`` at which
            the knee (and therefore the volume filter cutoff) was
            detected.
        norm_threshold (float): The normalised-volume value at
            ``index_threshold``, drawn as the horizontal threshold line.
        micrograph (str): Name of the tomogram being processed; used in
            the plot title and the output filename.
        output_dir (str or pathlib.Path): Job output directory. The plot
            is written under a ``plots`` subdirectory of this path.

    Raises:
        TypeError: If ``index_threshold`` is a string or float rather
            than an int.
        ValueError: If ``normalised_volume`` contains values outside
            [0, 1], i.e. it is not actually normalised.

    Note:
        Writes a PNG file to disk as its only meaningful output; no value
        is returned.
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

    # --- saving the figure
    plot_dir = Path(output_dir) / 'plots'
    plot_dir.mkdir(exist_ok=True)
    fig.savefig(plot_dir / f'{micrograph}_knee.png')
    close(fig)
