import argparse



# --- Building CLI parser
def build_parser():
    parser = argparse.ArgumentParser(prog='PickMe',
                                     description='CryoEM segmentation handling programme',
                                     usage='PickMe [options]')
    
    subparser = parser.add_subparsers(dest='job', required=True) #dest sets how the subcommand is accessed in the args, required ensures that a subcommand must be provided

    # --------------------------------
    # Subcommand 1: Object extraction
    # --------------------------------
    object_extract_parser = subparser.add_parser('filter_objects',
                                                 help='Identifies objects in a segmentaion and extracts and filters them')
    
    object_extract_parser.add_argument('--input-dir', required=True,
                                       type=str,
                                       help='Directory, pathlike, containing segmentation files of interest')
    
    object_extract_parser.add_argument('--output-dir', required=False,
                                       type=str,
                                       help='If users wish to have the output in a particular place, provide the path here.')
    
    object_extract_parser.add_argument('--filter', required=False,
                                       type=str,
                                       help='Choose method for filtering objects. Default: Max-Volume normalisation')
    
    # --------------------------------
    # Subcommand 2: Choosing objects
    # --------------------------------
    choice_parser = subparser.add_parser('choose_objects', 
                                         help='Choose objects within a segmentation of choice - uses Napari')
    choice_parser.add_argument('--input-dir', required=True,
                               type = str,
                               help = 'Directory contaning the reconstructed tomograms')
    choice_parser.add_argument('--segmentation-dir', required=False,
                               type = str,
                               help = 'If users have a segmentation that they want to pick specific objects, they can supply the directory of these. Here, we assume that the segmetation files are in mrc format.')
    choice_parser.add_argument('--output-dir', required=False,
                               type=str,
                               help='Users can select a desired directory to output this job - NOT RECOMMENDED')
    choice_parser.add_argument('--input-job', required=False,
                               type=int,
                               help='Use a specific filter job number (with segmentation) as input. For example, 1 selects job001.')
    choice_parser.add_argument('--write-selections', required = False,
                               action='store_true',
                               help='If users want to write selected objects as their own mrc files, in a subdirectory named by the tomogram ID, they can use this flag. By default, they are all written to the same mrc file.')
    
    # --------------------------------
    # Subcommand 3: Particle extraction
    # --------------------------------
    particle_extract_parser = subparser.add_parser('particle_extraction',
                                                   help='Take a set of segmentation objects and extract particles from the surface at a set pixel distance. Computing euler angles and generating STAR files')
    particle_extract_parser.add_argument('--input-dir', required=False,
                                         type=str,
                                         help='Supply directory path containing segmentations files you wish to sample. If Not provided, latest job from choose job will be used')
    particle_extract_parser.add_argument('--input-job', required=False,
                                         type = int,
                                         help='Users can supply a particular job number if they do not want to use latest from a Choose job. ENSURE to provide the three digit identifier i.e., 001')
    particle_extract_parser.add_argument('--output-dir', required=False,
                                         type=str,
                                         help='Pipeline output root. Defaults to ./outputs in the directory where PickMe is run.')
    particle_extract_parser.add_argument('--sample-rate', required=True,
                                         type = int,
                                         help='The sampling rate in pixels')
    particle_extract_parser.add_argument('--cmm', required=False,
                                         action='store_true',
                                         help='Enable writing of particle coordinates to a .cmm file')
    # --------------------------------
    # subcommand 4: Decmpression
    # --------------------------------
    decompress_parser = subparser.add_parser('decompress',
                                             help='Decompress mrc.gz or mrc.bz2 files into mrc - useful if you wish to view in Chimera')
    decompress_parser.add_argument('--input-dir', required = False,
                                   type=str,
                                   help='Directory containing the desired mrc.gz r mrc.bz2')
    decompress_parser.add_argument('--input-job', required = False,
                                   type = int,
                                   help='Can supply a job number from the PickMe pipeline')
    decompress_parser.add_argument('--output-dir', required=False,
                                   type=str,
                                   help='Pipeline output root. Defaults to ./outputs in the directory where PickMe is run.')



    # --------------------------------
    # subcommand5: Convert data types
    # --------------------------------
    convert_parser = subparser.add_parser('convert',
                                          help='Convert tomogram data types to a desired type - useful if you have a particular software that requires a specific data type')
    convert_parser.add_argument('--input-dir', required = True,
                                type = str,
                                help = 'Directory containing the tomograms you wish to convert')
    convert_parser.add_argument('--output-dir', required=False,
                                type=str,
                                help='Pipeline output root. Defaults to ./outputs in the directory where PickMe is run.')
    convert_parser.add_argument('--data-type', required = False,
                                type = str,
                                help = 'The data type you want to convert to. For example, float32 or int16. [DEFAULT: float32]')
    return parser
    


# --- Dispatching logic to functions
def main():
    parser = build_parser()
    args = parser.parse_args()
    #impotant to note - in subcommand options turns to _
    # e.g,. --input-dir = input_dir
    if args.job == 'filter_objects':
        from PickMe.main import filter_objects

        filter_objects(input_dir=args.input_dir,
                        filter_choice=args.filter,
                        output_dir=args.output_dir)
        
    if args.job == 'choose_objects':
        from PickMe.main import choose_object

        choose_object(input_dir=args.input_dir,
                      segmentation_dir=args.segmentation_dir,
                      input_job=args.input_job,
                      output_dir=args.output_dir,
                      write_selections=args.write_selections)
    if args.job == 'particle_extraction':
        from PickMe.main import particle_extract

        particle_extract(sample_rate=args.sample_rate,
                         cmm=args.cmm,
                         input_dir=args.input_dir,
                         input_job=args.input_job,
                         output_dir=args.output_dir)
    if args.job == 'decompress':
        from PickMe.main import decompress

        decompress(input_dir=args.input_dir,
                   input_job=args.input_job,
                   output_dir=args.output_dir)
    if args.job == 'convert':
        from PickMe.main import convert
        
        convert(input_dir=args.input_dir,
                output_dir=args.output_dir,
                data_type=args.data_type)
    return None
