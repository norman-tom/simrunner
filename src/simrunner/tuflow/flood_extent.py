import simrunner.tuflow as tfr

UTILITY = "C:\\tuflow\\utilities\\asc_to_asc\\asc_to_asc_w64.exe"
JOB_NUMBER = 24013
RESULT_ROOT = f"D:\\results\\{JOB_NUMBER}"
RN = "01"
METRIC = "h_Max"

def flood_extent(event: tfr.Run):
    # resolve the file paths
    result_dir = f"{RESULT_ROOT}\\processed{event.name}"