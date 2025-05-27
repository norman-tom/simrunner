import simrunner.tuflow as tfr
import os
import subprocess
from scripts.aggregate import strip_events

UTILITY = "C:\\tuflow\\utilities\\asc_to_asc\\asc_to_asc_w64.exe"
JOB_NUMBER = 24013
RESULT_ROOT = f"D:\\results\\{JOB_NUMBER}"
RN = "01"
METRIC = "h_Max"

def calc_afflux(baseline_event: tfr.Run, test_event: tfr.Run):
    # File structure for grids
    # <<results_root>>\<s1>\<s2>\<e1>\<e2>\2D\
    dir_base = f"{RESULT_ROOT}\\processed\\{baseline_event.s1}\\{baseline_event.s2}\\{baseline_event.e1}"
    dir_test = f"{RESULT_ROOT}\\processed\\{test_event.s1}\\{test_event.s2}\\{test_event.e1}"

    # Determine the file paths based on the events
    baseline_file = (
        f"max_{baseline_event.s1}_{baseline_event.s2}_{baseline_event.e1}_"
        f"{baseline_event.e4}_{baseline_event.e5}_01_{METRIC}.tif"
    )

    test_file = (
        f"max_{test_event.s1}_{test_event.s2}_{test_event.e1}_"
        f"{test_event.e4}_{test_event.e5}_01_{METRIC}.tif"
    )

    # check that the files exist
    if not os.path.exists(f"{dir_base}//{baseline_file}"):
        raise FileNotFoundError(f"Baseline file not found: {baseline_file}")

    if not os.path.exists(f"{dir_test}//{test_file}"):
        raise FileNotFoundError(f"Test file not found: {test_file}")
    
    # Output dir is the input dir with the difference appended
    out_dir = dir_test
    
    # Check that the directory exists and create it if it doesn't
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    
    output_file = (
        f"{out_dir}\\afflux_{test_event.s1}_{test_event.s2}_"
        f"{test_event.e1}_{test_event.e5}_{RN}_{METRIC}.tif"
    )

    args = [UTILITY, "-b", "-out", output_file, "-dif", f"{dir_test}//{test_file}", f"{dir_base}//{baseline_file}"]
    p = subprocess.run(args)

    return p.returncode

def elevation_afflux(base_events: list[tfr.Run], test_events: list[tfr.Run]):
    procesessed_base_events = strip_events(base_events, ("e2", "e3"))
    procesessed_test_events = strip_events(test_events, ("e2", "e3"))
    for base_event, test_event in zip(procesessed_base_events, procesessed_test_events):
        # Check if comparing the right events. 
        if (
            base_event.s2, base_event.e1, base_event.e4, base_event.e5) != (
            test_event.s2, test_event.e1, test_event.e4, test_event.e5):
            raise ValueError("Events do not match")
        calc_afflux(base_event, test_event)