# --- Setting up parameters and data structures ---
mgraph_suffix = '.tomostar'
star_suffix = '.star'


#instantiate the data structure to be used to write the star file
star_dict = {'rlnCoordinateX':[],
             'rlnCoordinateY':[],
             'rlnCoordinateZ':[],
             'rlnOriginX':[],
             'rlnOriginY':[],
             'rlnOriginZ':[],
             'rlnAngleRot':[],
             'rlnAngleTilt':[],
             'rlnAnglePsi':[],
             'rlnLCCmax':[],
             'rlnCutOff':[],
             'rlnSearchStd':[],
             'rlnDetectorPixelSize':[],
             'rlnMicrographName':[]} #This is .tomostar files -> TS_1234.tomostar

total_star_df = pd.DataFrame.from_dict(star_dict)
per_tomogram_star_df = total_star_df.copy()
#will make a particle row dictionary in a for loop within the segmentation mesh - loop over vertices
full_data_dict = {} #dictionary associating tomogram, with objects, and the objects data
