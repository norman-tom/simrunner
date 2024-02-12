import subprocess
import abc
import time

class Parameters:
    """
    The parameters of the model.

    Parameters:
        clone (Parameters): A Parameters object to clone.
        **kwargs: The parameters.
    """

    def __init__(self, clone: 'Parameters'=None, **kwargs):
        if clone is not None:
            self.__dict__ = clone.__dict__.copy()
        
        self.__dict__.update(kwargs)

    def __str__(self) -> str:
        return str(self.__dict__)
    
    def __repr__(self) -> str:
        return str(self.__dict__)
    
    def get_params(self):
        """
        Get the parameters.

        Returns:
            dict: A dictionary of the set parameters.
        """
        return self.__dict__
    
    @abc.abstractmethod
    def get_run_args(self) -> list[str]:
        """
        Get the required arguments to make a vaild run.
        """
        pass

class Run:
    """
    A single run of a model.

    Parameters:
        clone (Run): A Run object to clone.
        **kwargs: The run arguments.
    """

    def __init__(self, clone: 'Run'=None, **kwargs) -> None:
        if clone is not None: 
            self.__dict__ = clone.__dict__.copy()
        
        self.__dict__.update(kwargs)

    def __eq__(self, __value: object) -> bool:
        if not isinstance(__value, Run):
            return False
        
        return self.__dict__ == __value.__dict__
    
    def __str__(self) -> str:
        return str(self.__dict__)
    
    def __repr__(self) -> str:
        return str(self.__dict__)
    
    def get_args(self) -> dict:
        """
        Return the run arguments.

        Returns:
            dict: A dictionary of the run arguments.
        """
        return self.__dict__

class Runner:
    def __init__(self, parameters: Parameters, *args: 'Runner') -> None:
        self._parameters: Parameters = parameters
        self._runs: list[Run] = []
        self._index: int = 0

        for runner in args:
            for run in runner:
                self.stage(run)

    def __iter__(self) -> 'Runner':
        self._index = 0
        return self

    def __next__(self) -> Run:
        if self._index < len(self._runs):
            result = self._runs[self._index]
            self._index += 1
            return result
        raise StopIteration
    
    def __len__(self) -> int:
        return len(self._runs)

    def run(self, *run_numbers: list[str]) -> None:
        """
        Run all the staged runs.

        Parameters:
            *run_numbers (str): Variable number of run numbers to execute. If there is only one model, no run number is required. 
       """

        # Get flags from parameters, or use default
        try:
            flags = self._parameters.get_params()['flags']
        except KeyError:
            flags = None

        # Get the number of async runs from parameters, or use default
        try:
            async_runs = self._parameters.get_params()['async_runs']
        except KeyError:
            async_runs = 1

        if len(run_numbers) == 0:
            run_numbers = [None]

        processes: list[subprocess.Popen] = []
        for run in self:
            for rn in run_numbers:
                # if the queue is full, wait for a process to finish
                while len(processes) >= async_runs:
                    for p in processes:
                        return_code = p.poll()
                        if return_code is not None:
                            processes.remove(p)
                            if return_code != 0:
                                raise RunnerError(f"failed at run {self._index}:{self._runs[self._index-1]}")
                            break
                    time.sleep(1)

                # Run the command
                command = self._build_command(self._parameters, run, flags, rn)
                process = subprocess.Popen(command)
                processes.append(process)

                # Print the command that was run
                print(f"Running {command}")

        # Wait for all processes to finish
        for p in processes:
            p.wait()
            if p.returncode != 0:
                raise RunnerError(f"failed at run {self._index}:{self._runs[self._index-1]}")

    def stage(self, run: Run | list[Run]) -> None:
        """
        Adds a run/s to the list of runs for this model runner.

        Args:
            run (Run | list[Run]): The run/s to be added.

        Raises:
            RunnerError: If the provided run is not an instance of the Run class.
            RunnerError: If the run arguments do not match the required arguments.

        Returns:
            None
        """

        if isinstance(run, Run):
            run = [run]

        if not isinstance(run, list):
            raise RunnerError('run must be an instance of Run class or a list of Run objects')
        
        for r in run:
            self._stage_one(r)

    def _stage_one(self, run: Run) -> None:
        if not isinstance(run, Run):
            raise RunnerError('run must be an instance of Run class')
        
        run_args: set = set(run.get_args().keys())
        req_args: set = set(self._parameters.get_run_args())
        
        if run_args != req_args:
            raise RunnerError(f'run arguments do not match required arguments: {req_args}')

        if run not in self._runs:
            self._runs.append(run)

    def get_runs(self, *args: str, any=True):
        """
        Retrieves a list of runs based on the provided arguments.

        Parameters:
            *args (str): Variable number of arguments to filter the runs.
            any (bool): If True, returns runs that have any of the provided arguments.
                        If False, returns runs that have all of the provided arguments.

        Returns:
            list[Run]: A list of Run objects that match the provided arguments.
        """
       
        if len(args) == 0:
            return self._runs
        
        ret: list[Run] = []
        args: set = set(args)
        for run in self:
            run_args = set(run.get_args().values())
            if any:
                if args.intersection(run_args):
                    ret.append(run)
            else:
                if args.intersection(run_args) == args:
                    ret.append(run)

        return ret
    
    def remove_runs(self, runs: Run | list[Run]) -> None:
        """
        Removes the provided runs from the staged runs.

        Args:
            runs (list[Run]): A list of runs to be removed.

        Raises:
            RunnerError: If the provided runs are not instances of the Run class.

        Returns:
            None
        """

        if isinstance(runs, Run):
            runs = [runs]

        for run in runs:
            if not isinstance(run, Run):
                raise RunnerError(f'{run} - is not an instances of Run class')
            
            if run in self._runs:
                self._runs.remove(run)

    abc.abstractmethod
    def _build_command(self, parameters: Parameters, run: Run, *flags: list[str]) -> list[str]:
        """
        Build the command string to pass to subprocess.run(), this will be model dependent.
        """
        pass

class RunnerError(Exception):
    pass