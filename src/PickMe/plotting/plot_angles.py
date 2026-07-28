import seaborn as sns 
from matplotlib.pyplot import subplots
from pathlib import Path
from ..utils import check_make_dir


def plot_angles(star_data, output_dir, tomogram_name=None):
    """Save histograms of the tilt, rot, and psi Euler angle distributions.

    Plots the distribution (histogram + KDE) of each of the three Euler
    angles produced by `PickMe.angles.euler_star` — all in degrees — side
    by side, so biases in particle orientation can be spotted before
    downstream alignment. ``rlnAngleRot`` is drawn from a uniform random
    distribution by `PickMe.angles.euler_star`, so it should look flat
    here; ``rlnAngleTilt`` and ``rlnAnglePsi`` are derived from the actual
    membrane normals and may legitimately show some bias depending on
    membrane shape and sampling — the plot is for catching *extreme*
    biases, not enforcing a particular shape.

    Writes the figure to
    ``<output_dir>/AnglePlots/<tomogram_name>.png`` when ``tomogram_name``
    is given, or ``<output_dir>/AnglePlots/Angles_distribution.png``
    otherwise (the ``AnglePlots`` subdirectory is created if it does not
    already exist). Does not return anything.

    Args:
        star_data (pandas.DataFrame): STAR-file data containing at least
            the ``rlnAngleTilt``, ``rlnAngleRot``, and ``rlnAnglePsi``
            columns, as produced by `PickMe.angles.euler_star`.
        output_dir (str or pathlib.Path): Job output directory (e.g. the
            directory for the ``particle_extraction`` job) under which the
            ``AnglePlots`` subdirectory is created.
        tomogram_name (str, optional): Name of the tomogram being
            plotted, used for the output filename when plotting a single
            tomogram's angles. Defaults to None, which writes a single
            aggregate ``Angles_distribution.png`` instead.

    Note:
        Writes a PNG file to disk as its only meaningful output; no value
        is returned.
    """
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