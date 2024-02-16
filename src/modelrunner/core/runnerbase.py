import subprocess
import abc
import time

class ProcessQueue:
    """
    Manages the number of processes that can be run at once.
    """

    def __init__(self, max_processes: int) -> None:
        self._max_processes = max_processes
        self._processes: list[subprocess.Popen] = []

    def add(self, process: subprocess.Popen) -> None:
        """
        Add a process to the queue.

        Parameters:
            process (subprocess.Popen): The process to add.

        Returns:
            None
        """

        self._processes.append(process)

    def remove(self, process: subprocess.Popen) -> None:
        """
        Remove a process from the queue.

        Parameters:
            process (subprocess.Popen): The process to remove.

        Returns:
            None
        """

        self._processes.remove(process)

    def full(self) -> bool:
        """
        Check if the queue is full.

        Returns:
            bool: True if the queue is full, False otherwise.
        """

        return len(self._processes) >= self._max_processes

    def wait(self, sleep=0.1) -> None:
        """
        Wait until there is a free position in the process queue, allowing another processes to be added.
        Wait will block while the maximum number of processes are running.

        Raises:
            RunnerError: If a process returned a non zero exit code.
        
        Returns:
            None
        """

        while self.full():
            for p in self._processes:
                return_code = p.poll()
                if return_code is not None:
                    self._processes.remove(p)
                    if return_code != 0:
                        raise RunnerError(f"failed at run {p}")
                    break
            time.sleep(sleep)

    def wait_all(self) -> None:
        """
        Wait for all processes to finish.

        Raises:
            RunnerError: If a process returned a non zero exit code.

        Returns:
            None
        """

        for p in self._processes:
            p.wait()
            if p.returncode != 0:
                raise RunnerError(f"failed at run {p}")
            
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

        proc_queue = ProcessQueue(async_runs)
        for run in self:
            for rn in run_numbers:
                proc_queue.wait()
                command = self._build_command(self._parameters, run, flags, rn)
                proc_queue.add(subprocess.Popen(command))
                print(f"Running {command}")
        proc_queue.wait_all()

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
        """
        Adds a run to the list of runs for this model runner.

        Args:
            run (Run): The run to be added.

        Raises:
            RunnerError: If the provided run is not an instance of the Run class.
            RunnerError: If the run arguments do not match the required arguments.

        Returns:
            None
        """

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