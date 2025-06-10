from dataclasses import dataclass
from enum import Enum
from typing import Optional
import simrunner.tuflow as tfr
import os
import subprocess
import fnmatch
import shutil


class HydraulicMetric(Enum):
    HEAD = "h_Max"
    DEPTH = "d_Max"
    VELOCITY = "V_Max"


@dataclass
class UtilityConfig:
    tcf_template: str
    result_path_template: str
    output_template: str
    utility: str = "C:\\tuflow\\utilities\\asc_to_asc\\asc_to_asc_w64.exe"
    rn: str = "01"
    metric: HydraulicMetric = HydraulicMetric.HEAD

class RasterProcessor:
    def __init__(self, config: UtilityConfig):
        self._tcf_template = config.tcf_template
        self._result_template = config.result_path_template
        self._output_template = config.output_template
        self._utility = config.utility
        self._rn = config.rn
        self._metric = config.metric.value


    def _check_n_files(self, event: tfr.Run, dir: str, pattern: str) -> int:
        """Check the number of files in a directory that match a pattern.
        """
        for root, dirs, files in os.walk(dir):
            count = 0
            for file in files:
                if fnmatch.fnmatch(file, pattern):
                    count += 1
        return count


    def _strip_events(self, events: list[tfr.Run], parameter: tuple[str]) -> list[tfr.Run]:
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

    def _get_result_path(self, event: tfr.Run, out: bool = False) -> str:
        """ Maps a result template path to an actual path. The <<~s1~>>, <<~e1~>>... are tokens that will be 
        replaced with the event parameters; there can be any number and in any order. 
        'C:\\results\job_number\<<~s1~>>\<<~s2~>>\<<~e1~>>\<<~e2~>>\2D\\'  
        --> 'C:\\results\job_number\{event.s1}\{event.s2}\{event.e1}\{event.e2}\2D\grids' 
        """
        path = self._output_template if out else self._result_template
        event_args = event.get_args() 
        
        for arg_name, arg_value in event_args.items():
            token = f"<<~{arg_name}~>>"
            path = path.replace(token, str(arg_value))
            
        return path

    def _get_result_name(self, event: tfr.Run, /, drop: tuple[str, ...] | str = (), wild_card: Optional[str] = None) -> str:
        """
        Maps a tcf and event to the corresponding file name, for example;
        '24000_~s1~_~s2~_~e1~_~e2~_~e3~_~e4~_~e5~' -> '24000_exg_nb_1p_1440min_tp07_5pSS_2100_01_d_Max'.
        The drop parameter is used to drop a parameter from the event, for example if the event has e3, 
        but we want to drop it, we can pass 'e3' as the drop parameter. The wild_card parameter is used 
        to add a wildcard token '*' in place of the parameter, for example if the event has e3, but we 
        want to match any value for e3, we can pass 'e3' as the wild_card parameter. 
        """
        if isinstance(drop, str):
            drop = (drop,)
        
        name_template_parts = self._tcf_template.split('_')
        event_args = event.get_args()
        
        final_name_components = []
        for part in name_template_parts:
            if part.startswith('~') and part.endswith('~') and len(part) > 2:
                param_name = part[1:-1]  # Extract param_name from ~param_name~
                
                if param_name in drop:
                    # If this parameter is to be dropped, skip adding it.
                    continue
                elif param_name == wild_card:
                    final_name_components.append("*")
                elif param_name in event_args:
                    value = str(event_args[param_name])
                    if value: # Only add if the value is not an empty string
                        final_name_components.append(value)
                    # If value is empty, it's effectively dropped, similar to 'drop'
                else:
                    # Token in template, not dropped, not wildcard, not in event_args.
                    # This could be an error, or the token itself could be added if desired.
                    # For now, unresolvable tokens (not in event_args) are omitted.
                    # If specific error handling is needed, it can be added here.
                    raise ValueError(f"Token '{part}' not found in event args: {event_args}") 
            else:
                # This is a literal part (e.g., 'Group')
                if part: # Only add if the part is not an empty string
                    final_name_components.append(part)
        
        # Filter out any genuinely empty components that might have resulted from event arg values being empty strings
        # and were not caught by the `if value:` check above (e.g. if that check was removed).
        # Or if the tcf_name itself had parts that became empty after processing.
        base_name_parts = [comp for comp in final_name_components if comp]
        base_name = '_'.join(base_name_parts)
        
        # Append run number and metric
        if base_name:
            result_name = f"{base_name}_{self._rn}_{self._metric}"
        else:
            # If base_name is empty (e.g., all parts dropped or tcf_name was only tokens that were all dropped)
            # then form the name just from rn and metric, joined by an underscore if both exist.
            if self._rn and self._metric:
                result_name = f"{self._rn}_{self._metric}"
            elif self._rn:
                result_name = self._rn
            elif self._metric:
                result_name = self._metric
            else:
                raise ValueError("Cannot form a valid result name, not enough parametes provided.")
        
        return result_name


    def _aggregate_median(self, event: tfr.Run, parameter: str):
        # Directoy of the event files
        dir = self._get_result_path(event)

        # Check the input files directory exists
        if not os.path.exists(dir):
            raise FileNotFoundError(f"Directory {dir} does not exist")

        # Medians over the TP parameter.
        event_files = self._get_result_name(
            event, 
            wild_card=parameter  # Use a wildcard for the TP parameter
        ) + ".tif"

        # Check that the event_files exists in the directory
        if not fnmatch.filter(os.listdir(dir), event_files):
            raise FileNotFoundError(f"No files found matching pattern: {event_files} in directory {dir}")

        # Output file into a processed directory
        out_dir = self._get_result_path(event, out=True)
        
        # Check that the directory exists and create it if it doesn't
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)
        
        # File for the output
        output_file = f"{out_dir}\\median_{self._get_result_name(event, drop=parameter)}.tif"

        # Check the number of files is greater than 1
        count = self._check_n_files(event, dir, event_files)
        if count > 1:
            # If greater than 1, aggregate the files.
            args = [self._utility, "-b", "-out", output_file, "-statMedian", f"{dir}\\{event_files}"]
            p = subprocess.run(args)
            if p.returncode == 0:
                # Rename the output file to remove the _Median_Val from the name.
                files = os.listdir(out_dir)
                old = fnmatch.filter(files, f"median_{self._get_result_name(event, drop=parameter)}_Median_Val.tif")[0]
                if os.path.exists(output_file):
                    os.remove(output_file)
                os.rename(os.path.join(out_dir, old), output_file)
            return p.returncode
        elif count == 1:
            # If only one, copy the file to the output directory, 
            # and rename it as output_file.
            files = os.listdir(dir)
            file = fnmatch.filter(files, event_files)[0]
            if os.path.exists(output_file):
                os.remove(output_file)
            shutil.copy(os.path.join(dir, file), output_file)
            return 0
        else:
            raise FileNotFoundError("No files found to aggregate")
        

    def aggregate_tps(self, events: list[tfr.Run]):
        """
        Take the median of events over the TP parameter.
        """
        processed_events = self._strip_events(events, ("e3",))      # TODO: No hardcoded parameters, use the config.
        for event in processed_events:
            self._aggregate_median(event, 'e3')                     #TODO: No hardcoded parameters, use the config.


    def _aggregate_max(self, 
                       event: tfr.Run, 
                       parameter: str, 
                       ignore: Optional[tuple[str]] = None, 
                       ) -> int:
        """ Aggregate the maximum over a given parameter for a single event, 
        while optionally ignoring some parameters.

        Args:
            event (tfr.Run): The event to aggregate.
            parameter (str): The parameter to aggregate over, e.g., 'e2'.
            ignore (Optional[tuple[str]], optional): Parameters to ignore in the aggregation. Defaults to None.

        """            
        if ignore is None:
            ignore = ()

        # Get the event file path
        dir = self._get_result_path(event, out=True)

        # check the directory exists
        if not os.path.exists(dir):
            raise FileNotFoundError(f"Directory {dir} does not exist")

        # Aggregating over the duration parameter.
        event_files = f"median_{self._get_result_name(event, drop=ignore)}.tif" # TODO: this assumes that we want to aggregate the median files.

        # Check that the event_files exists in the directory
        filtered = fnmatch.filter(os.listdir(dir), event_files)
        if not filtered:
            raise FileNotFoundError(f"No files found matching pattern: {event_files} in directory {dir}")
        
        # Output file is the same directory as the input files
        out_dir = dir
        
        # Check that the directory exists and create it if it doesn't
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)

        output_file = f"{out_dir}\\max_{self._get_result_name(event, drop=(parameter, *ignore))}.tif" # TODO: Fix the drop parameter.

        # Check the number of files
        count = self._check_n_files(event, dir, event_files)
        if count > 1:
            # If greate than 1, aggregate the files
            args = [self._utility, "-b", "-out", output_file, "-max", f"{dir}\\{event_files}"]
            p = subprocess.run(args)
            return p.returncode
        elif count == 1:
            # If one file, copy the file to the output directory, 
            # and rename it as output_file
            files = os.listdir(dir)
            file = fnmatch.filter(files, event_files)[0]
            shutil.copy(os.path.join(dir, file), output_file)
            return 0
        else:
            raise FileNotFoundError(f"No files found to aggregate: {event}")
        
        
    def aggregate_duration(self, events: list[tfr.Run]):
        """
        Aggreagate the maximum over the duration parameter for a list of events.
        Assumes that the temporal patterns have already been aggregated to a single file per event.
        """
        processed_events = self._strip_events(events, ("e2", "e3")) # TODO: No hardcoded parameters, use the config.
        for event in processed_events:
            self._aggregate_max(event, 'e2', ('e3',))


    def _calc_afflux(self, base_event: tfr.Run, test_event: tfr.Run, ignore: Optional[tuple[str]] = None) -> int:
        """ Calculate the afflux between a base and test event."""
        if ignore is None:
            ignore = ()

        # File structure for grids
        dir_base = self._get_result_path(base_event, out=True)
        dir_test = self._get_result_path(test_event, out=True)

        # Determine the file paths based on the events
        # TODO: This assumes that the files are named as max_<event_name>.tif
        base_file = f"max_{self._get_result_name(base_event, drop=ignore)}.tif"
        test_file = f"max_{self._get_result_name(test_event, drop=ignore)}.tif"

        # Check that the directories exist
        if not os.path.exists(dir_base):
            raise FileNotFoundError(f"Base event directory {dir_base} does not exist")
        if not os.path.exists(dir_test):
            raise FileNotFoundError(f"Test event directory {dir_test} does not exist")
        
        # check that the files exist
        if not os.path.exists(f"{dir_base}//{base_file}"):
            raise FileNotFoundError(f"Base event file not found: {base_file}")
        if not os.path.exists(f"{dir_test}//{test_file}"):
            raise FileNotFoundError(f"Test event file not found: {test_file}")
        
        # Output dir is the input dir with the difference appended
        out_dir = dir_test
        
        # Check that the directory exists and create it if it doesn't
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)
        
        output_file = f"{out_dir}\\afflux_{self._get_result_name(test_event, drop=ignore)}.tif"

        args = [self._utility, "-b", "-out", output_file, "-dif", f"{dir_test}//{test_file}", f"{dir_base}//{base_file}"]
        p = subprocess.run(args)

        return p.returncode


    def elevation_afflux(self, base_events: list[tfr.Run], test_events: list[tfr.Run]):
        """ 
        Calculate the elevation afflux between a base and test event.
        Assumes that the events have already been aggregated on the TP and DUR parameters.
        """
        procesessed_base_events = self._strip_events(base_events, ("e2", "e3")) # TODO: No hardcoded parameters, use the config.
        procesessed_test_events = self._strip_events(test_events, ("e2", "e3")) # TODO: No hardcoded parameters, use the config.
        for base_event, test_event in zip(procesessed_base_events, procesessed_test_events):
            # Check if comparing the right events. 
            # TODO: This assumes that the events are in the same order and have the same parameters.
            if (
                base_event.s2, base_event.e1, base_event.e4, base_event.e5) != (
                test_event.s2, test_event.e1, test_event.e4, test_event.e5):
                raise ValueError("Events do not match")
            self._calc_afflux(base_event, test_event, ('e2', 'e3'))             # TODO: No hardcoded parameters, use the config.