import subprocess
import abc
import time
import threading
import os
import signal

class RunnerError(Exception):
    pass

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

        Returns:
            list[str]: A list of the required arguments.
        """
        pass

    def _check_required(self, required: list[str]) -> bool:
        """
        check that the required parameters have been set.

        Returns:
            bool: True if the required parameters have been set, False otherwise.
        """

        return set(required).issubset(set(self.__dict__.keys()))


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


class TaskQueue:
    """
    Manages the number of tasks that can be run at once. Used as a base class for ThreadQueue.

    Parameters:
        max_tasks (int): The maximum number of tasks that can be run at once.
    """

    def __init__(self, max_tasks: int) -> None:
        self._max_tasks = max_tasks
        self._tasks: list[None] = []

    def add(self, task: threading.Thread | subprocess.Popen) -> None:
        """
        Add a task to the queue.

        Returns:
            None
        """

        if len(self._tasks) < self._max_tasks:
            self._tasks.append(task)
        else:
            raise RunnerError('task queue is full, call wait() to wait for a free position in the queue.')

    def remove(self, task: threading.Thread | subprocess.Popen) -> None:
        """
        Remove a task from the queue.

        Returns:
            None
        """

        self._tasks.remove(task)

    def full(self) -> bool:
        """
        Check if the queue is full.

        Returns:
            bool: True if the queue is full, False otherwise.
        """

        return len(self._tasks) >= self._max_tasks

    abc.abstractmethod
    def wait(self, sleep=0.1) -> None:
        """
        Wait until there is a free position in the task queue, allowing another task to be added.
        Wait will block while the maximum number of tasks are running.

        Returns:
            None
        """
        pass
    
    abc.abstractmethod
    def wait_all(self, sleep=0.1) -> None:
        """
        Wait for all tasks to finish.

        Returns:
            None
        """
        pass


class ThreadQueue(TaskQueue):
    """
    Manages the number of threads that can be run at once.

    Parameters:
        max_threads (int): The maximum number of threads that can be run at once.
    """

    def __init__(self, max_threads: int) -> None:
        super().__init__(max_threads)
        self._tasks: list[threading.Thread] = []
        self._signal = None

    def add(self, task: threading.Thread | subprocess.Popen) -> None:
        # If termination is called, dont accept any more threads.
        if self._signal is not None:
            return None
        super().add(task)

    def wait(self, sleep=0.1) -> None:
        """
        Wait until there is a free position in the thread queue, allowing another threads to be added.
        Wait will block while the maximum number of threads are running.

        Returns:
            None
        """

        while self.full():
            for t in self._tasks:
                if not t.is_alive():
                    self._tasks.remove(t)
                    break
            try:
                time.sleep(sleep)
            except KeyboardInterrupt as e:
                raise e

    def wait_all(self) -> None:
        """
        Wait for all threads to finish.

        Returns:
            None
        """

        for t in self._tasks:
            t.join()
        self._threads = []

    def terminate(self) -> None:
        """
        Terminate all running threads.

        Returns:
            None
        """

        self._signal = signal.SIGINT
        for thread in self._tasks:
            os.kill(thread._process.pid, signal.CTRL_C_EVENT)


class Reporter:
    """
    An interface to report the output of a model run.
    """

    def __enter__(self) -> 'Reporter':	
        """
        Enter the context.

        Returns:
            self: The Reporter object.
        """
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """
        Exit the context.

        Args:
            exc_type (type): The type of the exception raised, if any.
            exc_value (Exception): The exception raised, if any.
            traceback (traceback): The traceback of the exception, if any.

        Returns:
            None
        """
        self.close()

    abc.abstractmethod
    def open(self) -> None:
        """
        Open the file with the specified mode.

        Args:
            mode (str): The mode to open the file in.

        Returns:
            None
        """
        pass
    
    abc.abstractmethod
    def close(self) -> None:
        """
        Close the file.

        Returns:
            None
        """
        pass
    
    abc.abstractmethod
    def write(self, content: str) -> None:
        """
        Write content to the file.

        Args:
            content (str): The content to write.

        Returns:
            None
        """
        pass


class FileReporter(Reporter):
    """
    A class to report the output of a model run to a file.

    Parameters:
        parameters (Parameters): The parameters of the model.
        run (Run): The run to report to.
        run_number (str): The file to report to.
    """

    def __init__(self, parameters: Parameters, run: Run, run_number: str) -> None:
        self._parameters = parameters
        self._file = self.__writeable(run, run_number)
        self._f = None

    def open(self) -> None:
        """
        Open the file with the specified mode.

        Args:
            mode (str): The mode to open the file in.

        Returns:
            None
        """
        self._f = open(self._file, 'w')

    def close(self) -> None:
        """
        Close the file.

        Returns:
            None
        """
        self._f.close()

    def write(self, content: str) -> None:
        """
        Write content to the file.

        Args:
            content (str): The content to write.

        Returns:
            None
        """
        self._f.write(content)

    def __writeable(self, run: Run, rn: str) -> str:
        """
        Returns the writable object to use for the reporter.

        For a FileReporter, this is the file name.
        """

        try:
            path = self._parameters.get_params()['stdout']
            if not os.path.exists(path):
                raise FileNotFoundError(f'{path} does not exist')
        except KeyError:
            path = os.getcwd()

        if rn is None:
            rn = 'NA'

        return os.path.join(path, f'run_{rn}_{list(run.get_args().values())}.out')


class ModelProcess(threading.Thread):
    """
    A thread that runs a model process.

    Parameters:
        command (list[str]): The command to run.
        reporter (Reporter): The Reporter to report outputs with.
    """

    def __init__(self, command: list[str], reporter: Reporter) -> None:
        super().__init__()
        self._command = command
        self._reporter = reporter
        self._process = None
        self.exc = None

    def execute(self, cmd):
        """
        Executes the subprocess and yields the stdout line by line.

        Args:
            cmd (list[str]): The command to run.
        Yields:
            str: The stdout line.
        """

        try:
            self._process = subprocess.Popen(cmd, stdout=subprocess.PIPE, universal_newlines=True)
        except FileNotFoundError as e:
            raise FileNotFoundError(f'executable "{cmd[0]}" cannot be found') from e
        except Exception as e:
            raise e
        
        for stdout_line in iter(self._process.stdout.readline, ""):
            yield stdout_line 
        
        self._process.stdout.close()
        return_code = self._process.wait()
        
        if return_code:
            # If the process was killed by a signal, return without error.
            if return_code == 2:
                return
            raise subprocess.CalledProcessError(return_code, cmd)
        
    def run(self) -> None:
        """
        Main thread method to run the model process.
        """

        try:
            with self._reporter as f:
                for out in self.execute(self._command):
                    f.write(out)
        except Exception as e:
            self.exc = e

    def join(self) -> None:
        """
        Wait for the thread to finish.

        Raises:
            Exception: If an exception was raised in the thread.

        Returns:
            None
        """

        try:
            super().join()
            if self.exc is not None:
                raise self.exc
        except KeyboardInterrupt:
            #TODO - Seems to be an issue with ipython and KeyboardInterrupt.
            # an exception is raised when the thread is joined, but the thread is still shuting down.
            pass
    
class Runner:
    """
    The Runner is responsible for queueing and running the model/s. 
    Runs are staged to the runner then executed when run is called. 
    Parameters are passed to the runner to config the runner.

    Parameters:
        parameters (Parameters): The parameters of the model.
        *args (Runner | None): Variable number of runners to add to this runner. 
        A runner can inherit runs from other runners, if required.
    """

    SIGINT = signal.SIGINT
    DONE = 1

    def __init__(self, parameters: Parameters, *args: 'Runner') -> None:
        self._lock = threading.Lock()
        self._thread_queue = None
        self._signal = self.DONE
        self._parameters: Parameters = parameters
        self._runs: list[Run] = []
        self._index: int = 0
        self._reporter = FileReporter

        # Set the signal handler.
        signal.signal(signal.SIGINT, self._signal_handler)

        # Stage all the runs from the provided runners.
        for runner in args:
            if isinstance(runner, Runner):
                for run in runner:
                    self._runs.append(run)

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
    
    def __getitem__(self, key: int) -> Run:
        return self._runs[key]

    def run(self, *run_numbers: list[str], blocking=False) -> None:
        """
        Run all the staged runs.

        Args:
            *run_numbers (str/s): Variable number of run numbers to execute. 
            If there is only one model, no run number is required. 

            blocking (bool): If True, the method will block until all runs are complete.
            else a new thread will be created to run the models.
       """
        
        # if still running, dont run again.
        if not self.done():
            return None
        
        if blocking:
            self._run(*run_numbers)
        else:
            threading.Thread(target=self._run, args=run_numbers).start()
    
    def _run(self, *run_numbers: list[str]) -> None:
        """
        Main model run loop. This method is called by the run method in 
        either a new thread or the main thread.
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

        # Deal with the run numbers.
        if len(run_numbers) == 0:
            run_numbers = [None]

        for rn in run_numbers:
            if rn is not None and not isinstance(rn, str):
                raise RunnerError('run number must be a string')

        # Main loop to run the models.
        self._signal = None
        self._thread_queue = ThreadQueue(async_runs)
        for run in self:
            if self._signal == self.SIGINT:
                break

            for rn in run_numbers:
                self._lock.acquire()

                try:
                    self._thread_queue.wait()
                except KeyboardInterrupt:
                    self._signal_handler(signal.SIGINT, None)

                if self._signal == self.SIGINT:
                    self._lock.release()
                    break
            
                command = self._build_command(self._parameters, run, flags, rn)
                reporter = self._reporter(self._parameters, run, rn)
                thread = ModelProcess(command, reporter)
                thread.start()
                self._thread_queue.add(thread)

                print(f"executing: {run}")

                self._lock.release()

        self._thread_queue.wait_all()

        if self._signal == self.SIGINT:
            print('---- ALL RUNS TERMINATED ----')
        else:
            print('---- ALL RUNS COMPLETE ----')
        self._signal = self.DONE

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
            raise RunnerError(f'run arguments: {run_args}, do not match required arguments: {req_args}')

        if run not in self._runs:
            self._runs.append(run)

    def get_runs(self, *args: str, any=True):
        """
        Retrieves a list of runs based on the provided arguments.

        Args:
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
        
    def stop(self) -> None:
        """
        Stops all models, gracefully.

        Returns:
            None
        """

        if self._signal != self.DONE:
            self._signal = self.SIGINT
            self._thread_queue.terminate()

    def pause(self) -> None:
        """
        Pauses all running models.

        Returns:
            None

        Raises:
            NotImplementedError: If the method is not implemented.
        """

        raise NotImplementedError('pause is not implemented')

    def resume(self) -> None:
        """
        Resumes all paused models.

        Returns:
            None
        
        Raises:
            NotImplementedError: If the method is not implemented.
        """

        raise NotImplementedError('resume is not implemented')
    
    def done(self) -> bool:
        """
        Check if all runs are complete.

        Returns:
            bool: True if all runs are complete, False otherwise.
        """

        return self._signal == self.DONE
    
    def _signal_handler(self, signal, frame):
        """
        Handler for the keyboard interrupt signal.
        """
        
        self.stop()

    abc.abstractmethod
    def _build_command(self, parameters: Parameters, run: Run, *flags: list[str]) -> list[str]:
        """
        Build the command string to pass to subprocess.run(), this will be model dependent.
        """
        pass