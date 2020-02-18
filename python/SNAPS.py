#!/anaconda3/bin/python3
# -*- coding: utf-8 -*-
"""
Main SNAPS script for assigning an observed shift list based on predicted shifts

@author: aph516
"""

def get_arguments(system_args):
    import argparse
    
    parser = argparse.ArgumentParser(
            description="SNAPS (Simple NMR Assignments from Predicted Shifts)")
    
    # Mandatory arguments
    parser.add_argument("shift_file", 
                        help="A table of observed chemical shifts.")
    parser.add_argument("pred_file",
                        help="A table of predicted chemical shifts.")
    parser.add_argument("output_file",
                        help="The file results will be written to.")
    
    # Information on input files and configuration options
    parser.add_argument("--shift_type", 
                        choices=["snaps", "ccpn", "sparky", "mars",
                                 "xeasy", "nmrpipe", "test"], 
                        default="snaps", 
                        help="The format of the observed shift file.")
    parser.add_argument("--pred_type", 
                        choices=["shiftx2", "sparta+"],
                        default="shiftx2", 
                        help="The format of the predicted shifts")
    parser.add_argument("--pred_seq_offset", type=int, default=0,
                        help="""An offset to apply to the residue numbering in 
                        the predicted shifts.""")
    parser.add_argument("-c", "--config_file", 
                        default="../config/config.txt",
                        help="A file containing parameters for the analysis.")
    parser.add_argument("--test_aa_classes", default=None, 
                        help="""For test data only. 
                        A string containing a comma-separated list of the amino acid 
                        classes for the i residue, a semicolon, then a list of AA 
                        classes for the i-1 residue. No spaces. 
                        eg. "ACDEFGHIKLMNPQRSTVWY;G,S,T,AVI,DN,FHYWC,REKPQML" for 
                        a sequential HADAMAC """)
    #TODO: Need to rethink how SS_class info is imported.
    
    # Options controlling output files
    parser.add_argument("-l", "--log_file", default=None,
                        help="A file logging information will be written to.")
    
    parser.add_argument("--shift_output_file", default=None,
                        help="""The file the assigned shiftlist will be written to.""")
    parser.add_argument("--shift_output_type", default="sparky",
                        choices=["sparky","xeasy","nmrpipe"],
                        help="One or more output formats for chemical shift export")
    parser.add_argument("--shift_output_confidence", nargs="*",
                        choices=["High","Medium","Low","Unreliable","Undefined"],
                        default=["High","Medium","Low","Unreliable","Undefined"],
                        help="""Limits the shiftlist output to assignments with 
                        particular confidence levels. More than one level is allowed""")
        
    parser.add_argument("--strip_plot_file", 
                        default=None,
                        help="A filename for an output strip plot.")
    parser.add_argument("--hsqc_plot_file", 
                        default=None,
                        help="A filename for an output HSQC plot.")
    
    
 
    args = parser.parse_args(system_args)
    if False:   # For convenience when testing
        args = parser.parse_args(("../data/P3a_L273R/naps_shifts_backbone.txt",
                                  "../data/P3a_L273R/shiftx2.cs",
                                  "../output/test.txt",
                                  "--shift_type","snaps",
                                  "--pred_type","shiftx2",
                                  "-c","../config/config_yaml.txt",
                                  "-l","../output/test.log"))  
    return(args)

def runSNAPS(system_args):
    """This function is used to run SNAPS from the command line, and in the original version of the web app."""
    from SNAPS_importer import SNAPS_importer
    from SNAPS_assigner import SNAPS_assigner
    import logging

    #### Command line arguments
    args = get_arguments(system_args)  

    #### Set up logging
    if args.log_file is not None:
        # Create a logger
        logger = logging.getLogger("SNAPS")
        logger.setLevel(logging.DEBUG)
        # Create a log handler that writes to a specific file.
        # In principle you could have multiple handlers, but here I just have one.
        # Need to explicitly define a handler so it can be explicitly closed 
        # once the analysis is complete.
        log_handler = logging.FileHandler(args.log_file, mode='w')
        log_handler.setLevel(logging.DEBUG)
        #log_handler.setFormatter(logging.Formatter("%(levelname)s %(asctime)s %(module)s %(funcName)s %(message)s"))
        log_handler.setFormatter(logging.Formatter(
                "%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S"))
        logger.addHandler(log_handler)

    else:
        logging.basicConfig(level=logging.ERROR)

    #### Set up the SNAPS_assigner object
    a = SNAPS_assigner()

    # Import config file
    a.read_config_file(args.config_file)
    

    # Import observed and predicted shifts
    importer = SNAPS_importer()

    if args.shift_type=="test":
        if args.test_aa_classes is None:
            importer.import_testset_shifts(args.shift_file)
        else:
            AA_class, AA_class_m1 = args.test_aa_classes.split(";")
            importer.import_testset_shifts(args.shift_file,
                                           SS_class=AA_class.split(","),
                                           SS_class_m1=AA_class_m1.split(","))
    else:
        importer.import_obs_shifts(args.shift_file, args.shift_type, SS_num=False)
        
    a.obs = importer.obs
    logger.info("Finished reading in %d spin systems from %s", 
                 len(a.obs["SS_name"]), args.shift_file)


    a.import_pred_shifts(args.pred_file, args.pred_type, args.pred_seq_offset)

    #### Do the analysis
    a.prepare_obs_preds()
    a.calc_log_prob_matrix()
    a.calc_mismatch_matrix()
    
    if a.pars["iterate_until_consistent"]:
        a.assign_df = a.find_consistent_assignments(set_assign_df=True)
    else:
        a.assign_from_preds(set_assign_df=True)
        a.add_consistency_info(threshold=a.pars["seq_link_threshold"])
    
    #### Output the results
    a.assign_df.to_csv(args.output_file, sep="\t", float_format="%.3f", 
                           index=False)
    
    logger.info("Finished writing results to %s", args.output_file)
    
    #### Write chemical shift lists
    if args.shift_output_file is not None:
        a.output_shiftlist(args.shift_output_file, args.shift_output_type, 
                           confidence_list=args.shift_output_confidence)
    
    #### Make some plots
    plots = []
    if args.hsqc_plot_file is not None:
        hsqc_plot = a.plot_hsqc(args.hsqc_plot_file, "html")
        logger.info("Finished writing HSQC plot to %s", args.hsqc_plot_file)
        plots += [hsqc_plot]
        
    if args.strip_plot_file is not None:
        strip_plot = a.plot_strips(args.strip_plot_file, "html")
        logger.info("Finished writing strip plot to %s", args.strip_plot_file)
        plots += [strip_plot]
    
    # Close the log file
    logger.handlers[0].close()
    logger.removeHandler(logger.handlers[0])

    return(plots)

def SNAPS_compute(shift_file, shift_type, pred_file, pred_type):
    """Run SNAPS from webApp2"""
    from SNAPS_assigner import SNAPS_assigner
    from SNAPS_importer import SNAPS_importer
    import logging
    
    # Set up logging
    web_logger = logging.getLogger("SNAPS")
    web_logger.setLevel(logging.DEBUG)
    # Create a log handler that writes to a specific file.
    # In principle you could have multiple handlers, but here I just have one.
    # Need to explicitly define a handler so it can be explicitly closed 
    # once the analysis is complete.
    log_handler = logging.FileHandler("logs/webApp.log", mode='a')
    log_handler.setLevel(logging.DEBUG)
    log_handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(message)s", 
            datefmt="%Y-%m-%d %H:%M:%S"))
    web_logger.addHandler(log_handler)
    
    web_logger.info("**** STARTING NEW SNAPS RUN ****")
    
    #### Prepare the input data
    a = SNAPS_assigner()
    a.read_config_file("../config/config_yaml.txt")
    
    # Import observed shifts
    importer = SNAPS_importer()

    if shift_type=="test":
        importer.import_testset_shifts(shift_file)       
    else:
        importer.import_obs_shifts(shift_file, shift_type, SS_num=False)
        
    a.obs = importer.obs    
    web_logger.info("Finished reading in %d spin systems from %s", 
                 len(a.obs["SS_name"]), shift_file)
    
    # Import predicted shifts
    a.import_pred_shifts(pred_file, pred_type, 0)
    
    #### Do the calculations
    a.prepare_obs_preds()
    a.calc_log_prob_matrix()
    a.calc_mismatch_matrix()
    
    if a.pars["iterate_until_consistent"]:
        a.find_consistent_assignments(set_assign_df=True)
    else:
        a.assign_from_preds(set_assign_df=True)
        a.add_consistency_info(threshold=a.pars["seq_link_threshold"])
        
    #### Return the results
    # Get the main results table
    results_table = a.assign_df.to_csv(None, sep="\t", float_format="%.3f", 
                           index=False)
    
    # Get the assigned chemical shift list
    shiftlist = a.output_shiftlist(None, "sparky", 
                       confidence_list=["High","Medium","Low","Unreliable","Undefined"])
    
    # Make the plots
    hsqc_plot = a.plot_hsqc(return_json=False)
        
    strip_plot = a.plot_strips(return_json=False)
    
    # Close the log file
    web_logger.info("SNAPS run complete.")
    web_logger.handlers[0].close()
    web_logger.removeHandler(web_logger.handlers[0])
        
    return {"main_results":results_table, "shiftlist":shiftlist}, {"hsqc_plot":hsqc_plot, "strip_plot":strip_plot}

#%% Run the actual script
if __name__ == '__main__':
    import sys

    runSNAPS(sys.argv[1:])
