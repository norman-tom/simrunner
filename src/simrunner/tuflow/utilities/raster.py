import fnmatch
import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import simrunner.tuflow as tfr


class HydraulicMetric(Enum):
    HEAD = "h_Max"
    DEPTH = "d_Max"
    VELOCITY = "V_Max"


class AggregationOperation(Enum):
    MEDIAN = "statMedian"
    MAX = "max"


@dataclass
class ParameterMap:
    """Map the tcf parameter """
    aep: str
    duration: str
    temporal_pattern: str

@dataclass
class UtilityConfig:
    tcf_template: str
    parameter_map: ParameterMap
    result_path_template: str
    output_template: str
    utility: str = "C:\\tuflow\\utilities\\asc_to_asc\\asc_to_asc_w64.exe"
    rn: str = "01"
    metric: HydraulicMetric = HydraulicMetric.HEAD


class AggregationStrategy(ABC):
    """Abstract base class for different aggregation strategies."""

    @abstractmethod
    def get_operation_arg(self) -> str:
        """Return the command-line argument for the aggregation operation."""
        pass

    @abstractmethod
    def get_output_prefix(self) -> str:
        """Return the prefix for output files."""
        pass

    @abstractmethod
    def process_output_file(self, expected_output: str, actual_output_dir: str) -> None:
        """Handle any post-processing of the output file (e.g., renaming)."""
        pass


class MedianAggregationStrategy(AggregationStrategy):
    def get_operation_arg(self) -> str:
        return "-statMedian"

    def get_output_prefix(self) -> str:
        return "median"

    def process_output_file(self, expected_output: str, actual_output_dir: str) -> None:
        """Handle renaming of median output file which has '_Median_Val' suffix."""
        files = os.listdir(actual_output_dir)
        base_name = os.path.basename(expected_output)
        # Look for the file with _Median_Val suffix
        median_pattern = base_name.replace('.tif', '_Median_Val.tif')
        matching_files = fnmatch.filter(files, median_pattern)

        if matching_files:
            old_file = os.path.join(actual_output_dir, matching_files[0])
            if os.path.exists(expected_output):
                os.remove(expected_output)
            os.rename(old_file, expected_output)


class MaxAggregationStrategy(AggregationStrategy):
    def get_operation_arg(self) -> str:
        return "-max"

    def get_output_prefix(self) -> str:
        return "max"

    def process_output_file(self, expected_output: str, actual_output_dir: str) -> None:
        """No post-processing needed for max aggregation."""
        pass


class RasterProcessor:
    def __init__(self, config: UtilityConfig):
        self._tcf_template = config.tcf_template
        self._result_template = config.result_path_template
        self._output_template = config.output_template
        self._utility = config.utility
        self._rn = config.rn
        self._metric = config.metric.value
        self._parameter_map = config.parameter_map

    def _check_n_files(self, event: tfr.Run, dir: str, pattern: str) -> int:
        """Check the number of files in a directory that match a pattern."""
        for root, dirs, files in os.walk(dir):
            count = 0
            for file in files:
                if fnmatch.fnmatch(file, pattern):
                    count += 1
        return count

    def _strip_events(self, events: list[tfr.Run], parameter: tuple[str]) -> list[tfr.Run]:
        """For a list of events, cluster them based on their shared parameters, ignoring the passed parameters,
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
        """Maps a result template path to an actual path. The <<~s1~>>, <<~e1~>>... are tokens that will be
        replaced with the event parameters; there can be any number and in any order.
        # Example:
        If the result template is '/results/job_number/<<~s1~>>/<<~s2~>>/<<~e1~>>/<<~e2~>>/2D'
        and the event has the following parameters:
        s1 = "exg", s2 = "1440min", e1 = "tp07", e2 = "5pSS"
        then the resulting path will be:
        '/results/job_number/exg/1440min/tp07/5pSS/2D'.
        """
        path = self._output_template if out else self._result_template
        event_args = event.get_args()

        for arg_name, arg_value in event_args.items():
            token = f"<<~{arg_name}~>>"
            path = path.replace(token, str(arg_value))

        return path

    def _get_result_name(
        self, event: tfr.Run, /, drop: tuple[str, ...] | str = (), wild_card: Optional[str] = None
    ) -> str:
        """Maps a tcf and event to the corresponding file name, for example;
        '24000_~s1~_~s2~_~e1~_~e2~_~e3~_~e4~_~e5~' -> '24000_exg_nb_1p_1440min_tp07_5pSS_2100_01_d_Max'.
        The drop parameter is used to drop a parameter from the event, for example if the event has e3,
        but we want to drop it, we can pass 'e3' as the drop parameter. The wild_card parameter is used
        to add a wildcard token '*' in place of the parameter, for example if the event has e3, but we
        want to match any value for e3, we can pass 'e3' as the wild_card parameter.
        """
        if isinstance(drop, str):
            drop = (drop,)

        name_template_parts = self._tcf_template.split("_")
        event_args = event.get_args()

        final_name_components = []
        for part in name_template_parts:
            if part.startswith("~") and part.endswith("~") and len(part) > 2:
                param_name = part[1:-1]  # Extract param_name from ~param_name~

                if param_name in drop:
                    # If this parameter is to be dropped, skip adding it.
                    continue
                elif param_name == wild_card:
                    final_name_components.append("*")
                elif param_name in event_args:
                    value = str(event_args[param_name])
                    if value:  # Only add if the value is not an empty string
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
                if part:  # Only add if the part is not an empty string
                    final_name_components.append(part)

        # Filter out any genuinely empty components that might have resulted from event arg values being empty strings
        # and were not caught by the `if value:` check above (e.g. if that check was removed).
        # Or if the tcf_name itself had parts that became empty after processing.
        base_name_parts = [comp for comp in final_name_components if comp]
        base_name = "_".join(base_name_parts)

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

    def _validate_directory_exists(self, directory: str, description: str) -> None:
        """Validate that a directory exists, raising FileNotFoundError if not."""
        if not os.path.exists(directory):
            raise FileNotFoundError(f"{description} directory {directory} does not exist")

    def _ensure_directory_exists(self, directory: str) -> None:
        """Ensure a directory exists, creating it if necessary."""
        if not os.path.exists(directory):
            os.makedirs(directory)

    def _construct_file_pattern(self, base_name: str, file_prefix: str) -> str:
        """Construct file pattern with optional prefix."""
        if file_prefix:
            if not file_prefix.endswith('_'):
                file_prefix += '_'
            return f"{file_prefix}{base_name}.tif"
        return f"{base_name}.tif"

    def _validate_files_exist(self, directory: str, pattern: str) -> None:
        """Validate that files matching the pattern exist in the directory."""
        if not fnmatch.filter(os.listdir(directory), pattern):
            raise FileNotFoundError(f"No files found matching pattern: {pattern} in directory {directory}")

    def _handle_single_file_case(self, source_dir: str, pattern: str, output_file: str) -> int:
        """Handle the case where only one file matches the pattern - copy it to output."""
        files = os.listdir(source_dir)
        file = fnmatch.filter(files, pattern)[0]
        if os.path.exists(output_file):
            os.remove(output_file)
        shutil.copy(os.path.join(source_dir, file), output_file)
        return 0

    def _aggregate_files(
        self,
        event: tfr.Run,
        parameter: str,
        strategy: AggregationStrategy,
        ignore: Optional[tuple[str]] = None,
        file_prefix: str = "",
        input_from_output_dir: bool = False
    ) -> int:
        """
        Generic aggregation method that handles both median and max operations.

        Args:
            event: The event to aggregate
            parameter: The parameter to aggregate over (used for wildcards/dropping)
            strategy: The aggregation strategy to use
            ignore: Additional parameters to ignore (used with drop for output naming)
            file_prefix: Prefix for input files
            input_from_output_dir: Whether to read input files from output directory
        """
        if ignore is None:
            ignore = ()

        # Determine input directory
        input_dir = self._get_result_path(event, out=input_from_output_dir)
        self._validate_directory_exists(input_dir, "Input")

        # Determine output directory
        output_dir = self._get_result_path(event, out=True)
        self._ensure_directory_exists(output_dir)


        input_base_name = self._get_result_name(event, drop=ignore, wild_card=parameter)
        output_base_name = self._get_result_name(event, drop=(parameter, *ignore))

        input_pattern = self._construct_file_pattern(input_base_name, file_prefix)
        self._validate_files_exist(input_dir, input_pattern)

        # Construct output file path
        output_prefix = strategy.get_output_prefix()
        output_file = f"{output_dir}\\{output_prefix}_{output_base_name}.tif"

        # Check number of files and proceed accordingly
        file_count = self._check_n_files(event, input_dir, input_pattern)

        if file_count > 1:
            # Multiple files - run aggregation utility
            args = [
                self._utility,
                "-b",
                "-out",
                output_file,
                strategy.get_operation_arg(),
                f"{input_dir}\\{input_pattern}"
            ]
            process = subprocess.run(args)

            if process.returncode == 0:
                strategy.process_output_file(output_file, output_dir)

            return process.returncode

        elif file_count == 1:
            # Single file - copy to output
            return self._handle_single_file_case(input_dir, input_pattern, output_file)
        else:
            raise FileNotFoundError(f"No files found to aggregate for event: {event}")

    def _aggregate_median(self, event: tfr.Run, parameter: str, file_prefix: str = "") -> int:
        """Aggregate the median over a given parameter for a single event."""
        strategy = MedianAggregationStrategy()
        return self._aggregate_files(
            event=event,
            parameter=parameter,
            strategy=strategy,
            file_prefix=file_prefix,
            input_from_output_dir=False
        )

    def _aggregate_max(
        self,
        event: tfr.Run,
        parameter: str,
        ignore: Optional[tuple[str]] = None,
        file_prefix: str = "",
    ) -> int:
        """Aggregate the maximum over a given parameter for a single event."""
        strategy = MaxAggregationStrategy()
        return self._aggregate_files(
            event=event,
            parameter=parameter,
            strategy=strategy,
            ignore=ignore,
            file_prefix=file_prefix,
            input_from_output_dir=True
        )

    def aggregate_tps(self, events: list[tfr.Run]) -> None:
        """Take the median of events over the TP parameter."""
        processed_events = self._strip_events(events, (self._parameter_map.temporal_pattern,))
        for event in processed_events:
            self._aggregate_median(event, self._parameter_map.temporal_pattern, file_prefix="")

    def aggregate_duration(self, events: list[tfr.Run]) -> None:
        """Aggreagate the maximum over the duration parameter for a list of events.
        Assumes that the temporal patterns have already been aggregated to a single file per event.
        """
        processed_events = self._strip_events(
            events, (self._parameter_map.duration, self._parameter_map.temporal_pattern)
        )
        median_prefix = MedianAggregationStrategy().get_output_prefix()
        for event in processed_events:
            self._aggregate_max(
                event,
                self._parameter_map.duration,
                (self._parameter_map.temporal_pattern,),
                f"{median_prefix}_"
            )

    def _calc_afflux(self, base_event: tfr.Run, test_event: tfr.Run, ignore: Optional[tuple[str]] = None) -> int:
        """Calculate the afflux between a base and test event."""
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

        args = [
            self._utility,
            "-b",
            "-out",
            output_file,
            "-dif",
            f"{dir_test}//{test_file}",
            f"{dir_base}//{base_file}",
        ]
        p = subprocess.run(args)

        return p.returncode

    def elevation_afflux(
            self, base_events: list[tfr.Run], test_events: list[tfr.Run], parameter: Optional[str] = None
        ) -> None:
        """Calculate the elevation afflux between a base and test event.
        Assumes that the events have already been aggregated on the TP and DUR parameters.
        """
        ignore_params = (self._parameter_map.duration, self._parameter_map.temporal_pattern)

        if parameter in ignore_params:
            raise ValueError(f'parameter: {parameter} cannot be either {ignore_params[0]} or {ignore_params[0]}')

        procesessed_base_events = self._strip_events(
            base_events, ignore_params
        )
        procesessed_test_events = self._strip_events(
            test_events, ignore_params
        )

        for base_event, test_event in zip(procesessed_base_events, procesessed_test_events):
            if parameter:
                # If a parameter is given check if events only differ by that variable.
                # Dynamically create keys for comparison by excluding ignored parameters.
                ignore = (parameter, *ignore_params)
                base_key_params = {
                    k: v for k, v in base_event.get_args().items()
                    if k not in ignore
                }
                test_key_params = {
                    k: v for k, v in test_event.get_args().items()
                    if k not in ignore
                }

                if base_key_params != test_key_params:
                    raise ValueError(
                        f"Events do not match for afflux calculation. Base: {base_key_params}, Test: {test_key_params}"
                    )
            self._calc_afflux(base_event, test_event, ignore_params)
