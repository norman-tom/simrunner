import simrunner.tuflow as tfr
import os
import subprocess
import fnmatch
import shutil

UTILITY = "C:\\tuflow\\utilities\\asc_to_asc\\asc_to_asc_w64.exe"
JOB_NUMBER = 24013
RESULT_ROOT = f"D:\\results\\{JOB_NUMBER}"
RN = "01"
METRIC = "h_Max"

def check_n_files(event: tfr.Run, dir: str, pattern: str) -> int:
    for root, dirs, files in os.walk(dir):
        count = 0
        for file in files:
            if fnmatch.fnmatch(file, pattern):
                count += 1
    return count

def strip_events(events: list[tfr.Run], parameter: tuple[str]) -> list[tfr.Run]:
    """
    For a list of events, cluster them based on their shared parameters, ignoring the passed parameters,
    and return a representative event. For example, if the parameter is e1, then all the events 
    that have the same value for parameters s1, s2, e2, e3, e4, e5 will be clustered and represented by
    a single event. The first event found will be the representative event.
    """
    representative_events = {}
    for event in events:
        # Determine the key, which is all the parameters except for the ignored parameter.
        key = tuple([value for arg, value in event.get_args().items() if arg not in parameter])
        if key not in representative_events:
            representative_events[key] = event
    return list(representative_events.values())


def aggregate_median(event: tfr.Run):
    # Directoy of the event files
    dir = (
        f"{RESULT_ROOT}\\{event.s1}\\{event.s2}\\"
        f"{event.e1}\\{event.e2}\\2D\\grids"
    )

    # Check the input files directory exists
    if not os.path.exists(dir):
        raise FileNotFoundError(f"Directory {dir} does not exist")

    # Medians over the TP parameter.
    event_files = (
        f"{JOB_NUMBER}_{event.s1}_{event.s2}_"
        f"{event.e1}_{event.e2}_*_"
        f"{event.e4}_{event.e5}_{RN}_{METRIC}.tif"
    )

    # Output file into a processed directory
    out_dir = f"{RESULT_ROOT}\\processed\\{event.s1}\\{event.s2}\\{event.e1}"
    
    # Check that the directory exists and create it if it doesn't
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    
    # File for the output
    output_file = (
        f"{out_dir}\\median_{event.s1}_{event.s2}_"
        f"{event.e1}_{event.e2}_{event.e4}_{event.e5}_{RN}_{METRIC}.tif"
    )

    # Check the number of files is greater than 1
    count = check_n_files(event, dir, event_files)
    if count > 1:
        # If greater than 1, aggregate the files.
        args = [UTILITY, "-b", "-out", output_file, "-statMedian", f"{dir}\\{event_files}"]
        p = subprocess.run(args)
        return p.returncode
    elif count == 1:
        # If only one, copy the file to the output directory, 
        # and rename it as output_file.
        files = os.listdir(dir)
        file = fnmatch.filter(files, event_files)[0]
        shutil.copy(os.path.join(dir, file), output_file)
        return 0
    else:
        raise FileNotFoundError("No files found to aggregate")
    
def aggregate_tps(events: list[tfr.Run]):
    """
    Aggreagate the median over the TP parameter for a list of events.
    """
    processed_events = strip_events(events, ("e3",))
    for event in processed_events:
        aggregate_median(event)


def aggregate_max(event: tfr.Run):
    # Get the event file path
    dir = f"{RESULT_ROOT}\\processed\\{event.s1}\\{event.s2}\\{event.e1}"

    # check the directory exists
    if not os.path.exists(dir):
        raise FileNotFoundError(f"Directory {dir} does not exist")

    # Aggregating over the duration parameter.
    event_files = (
        f"median_{event.s1}_{event.s2}_{event.e1}_"
        f"*_{event.e4}_{event.e5}_{RN}_{METRIC}.tif"
    )

    # Output file is the same directory as the input files
    out_dir = dir
    
    # Check that the directory exists and create it if it doesn't
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    
    output_file = (
        f"{out_dir}\\"
        f"max_{event.s1}_{event.s2}_"
        f"{event.e1}_{event.e4}_{event.e5}_{RN}_{METRIC}.tif"
    )

    # Check the number of files
    count = check_n_files(event, dir, event_files)
    if count > 1:
        # If greate than 1, aggregate the files
        args = [UTILITY, "-b", "-out", output_file, "-max", f"{dir}\\{event_files}"]
        p = subprocess.run(args)
        return p.returncode
    elif count == 1:
        # If one file, copy the file to the output directory, 
        # and rename it as output_file
        files = os.listdir(dir)
        file = fnmatch.filter(files, (
                f"median_{event.s1}_{event.s2}_"
                f"{event.e1}_*_{event.e4}_{event.e5}_{RN}_{METRIC}.tif"
                )
            )[0]
        shutil.copy(os.path.join(dir, file), output_file)
        return 0
    else:
        raise FileNotFoundError(f"No files found to aggregate: {event}")
    
def aggregate_duration(events: list[tfr.Run]):
    """
    Aggreagate the max over the duration parameter for a list of events.
    """
    processed_events = strip_events(events, ("e2", "e3"))
    for event in processed_events:
        aggregate_max(event)