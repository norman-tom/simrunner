import abc
import os
import signal
import subprocess
import threading
import time


class RunnerError(Exception):
    pass


class Parameters:
    """The parameters of the model.

    Parameters:
        clone (Parameters): A Parameters object to clone.
        **kwargs: The parameters.
    """

    def __init__(self, clone: "Parameters" = None, **kwargs):
        if clone is not None:
            self.__dict__ = clone.__dict__.copy()

        self.__dict__.update(kwargs)

    def __str__(self) -> str:
        return str(self.__dict__)

    def __repr__(self) -> str:
        return str(self.__dict__)

    def get_params(self):
        """Get the parameters.

        Returns:
            dict: A dictionary of the set parameters.
        """
        return self.__dict__

    @abc.abstractmethod
    def get_run_args(self) -> list[str]:
        """Get the required arguments to make a vaild run.

        Returns:
            list[str]: A list of the required arguments.
        """
        pass

    def _check_required(self, required: list[str]) -> bool:
        """Check that the required parameters have been set.

        Returns:
            bool: True if the required parameters have been set, False otherwise.
        """
        return set(required).issubset(set(self.__dict__.keys()))


class Run:
    """A single run of a model.

    Parameters:
        clone (Run): A Run object to clone.
        **kwargs: The run arguments.
    """

    def __init__(self, clone: "Run" = None, **kwargs) -> None:
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
        """Return the run arguments.

        Returns:
            dict: A dictionary of the run arguments.
        """
        return self.__dict__


class TaskQueue:
    """Manages the number of tasks that can be run at once. Used as a base class for ThreadQueue.

    Parameters:
        max_tasks (int): The maximum number of tasks that can be run at once.
    """

    def __init__(self, max_tasks: int) -> None:
        self._lock = threading.Lock()
        self._max_tasks = max_tasks
        self._running_tasks: list = []
        self._tasks: list = []

    @abc.abstractmethod
    def start(self, task: threading.Thread | subprocess.Popen) -> None:
        """Start a task.

        Returns:
            None
        """
        pass

    def add(self, task: threading.Thread | subprocess.Popen) -> None:
        """Add a task to the queue.

        Returns:
            None
        """
        self._tasks.append(task)

    def remove(self, task: threading.Thread | subprocess.Popen) -> None:
        """Remove a task from the queue.

        Returns:
            None
        """
        self._tasks.remove(task)

    def full(self) -> bool:
        """Check if the queue is full.

        Returns:
            bool: True if the queue is full, False otherwise.
        """
        return len(self._running_tasks) >= self._max_tasks

    abc.abstractmethod

    def wait(self, sleep=0.1) -> None:
        """Wait until there is a free position in the task queue, allowing another task to be added.
        Wait will block while the maximum number of tasks are running.

        Returns:
            None
        """
        pass

    abc.abstractmethod

    def wait_all(self, sleep=0.1) -> None:
        """Wait for all tasks to finish.

        Returns:
            None
        """
        pass


class ThreadQueue(TaskQueue):
    """Manages the number of threads that can be run at once.

    Parameters:
        max_threads (int): The maximum number of threads that can be run at once.
        stop_event (threading.Event): The event to interupt the threads.
    """

    def __init__(self, max_threads: int, stop_event) -> None:
        super().__init__(max_threads)
        self._tasks: list[threading.Thread] = []
        self._running_tasks: list[threading.Thread] = []
        self._index = 0
        self._stop_event = stop_event

    def __iter__(self) -> "ThreadQueue":
        self._index = 0
        return self

    def __next__(self) -> threading.Thread:
        # If we are at the end of the list, wait for all threads to finish.
        if self._index >= len(self._tasks):
            try:
                self.wait_all()
                raise StopIteration
            except KeyboardInterrupt:
                self.interupt()
                raise StopIteration
            except Exception as e:
                raise e

        # Wait for a free position in the thread queue.
        try:
            self.wait()
        except KeyboardInterrupt:
            self.interupt()
            raise StopIteration

        result = self._tasks[self._index]
        self._index += 1
        return result

    def start(self, task: threading.Thread) -> None:
        """Start a task that is managed by the thread queue."""
        self._lock.acquire()
        task.start()
        self._running_tasks.append(task)
        self._lock.release()

    def wait(self, sleep=0.1) -> None:
        """Wait until there is a free position in the thread queue, allowing
        another threads to be added. Wait will block while the maximum number
        of threads are running.

        Returns:
            None

        Raises:
            KeyboardInterrupt: If a keyboard interrupt is raised.
        """
        self._lock.acquire()
        while self.full():
            if self._stop_event.is_set():
                self._lock.release()
                raise KeyboardInterrupt

            for t in self._running_tasks:
                if not t.is_alive():
                    self._running_tasks.remove(t)
                    break
            time.sleep(sleep)

        self._lock.release()

    def wait_all(self) -> None:
        """Wait for all threads to finish.

        Returns:
            None

        Raises:
            KeyboardInterrupt: If a keyboard interrupt is raised.
        """
        for t in self._running_tasks:
            t.join()

    def interupt(self) -> None:
        """Interupts all running threads by sending a CTRL-C event.

        Returns:
            None
        """
        self._lock.acquire()
        for task in self._running_tasks:
            if task.is_alive():
                os.kill(task._process.pid, signal.CTRL_C_EVENT)
        self._lock.release()


class Reporter:
    """An interface to report the output of a model run."""

    def __enter__(self) -> "Reporter":
        """Enter the context.

        Returns:
            self: The Reporter object.
        """
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Exit the context.

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
        """Open the file with the specified mode.

        Args:
            mode (str): The mode to open the file in.

        Returns:
            None
        """
        pass

    abc.abstractmethod

    def close(self) -> None:
        """Close the file.

        Returns:
            None
        """
        pass

    abc.abstractmethod

    def write(self, content: str) -> None:
        """Write content to the file.

        Args:
            content (str): The content to write.

        Returns:
            None
        """
        pass


class FileReporter(Reporter):
    """A class to report the output of a model run to a file.

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
        """Open the file with the specified mode.

        Args:
            mode (str): The mode to open the file in.

        Returns:
            None
        """
        self._f = open(self._file, "w")

    def close(self) -> None:
        """Close the file.

        Returns:
            None
        """
        self._f.close()

    def write(self, content: str) -> None:
        """Write content to the file.

        Args:
            content (str): The content to write.

        Returns:
            None
        """
        self._f.write(content)

    def __writeable(self, run: Run, rn: str) -> str:
        """Returns the writable object to use for the reporter.

        For a FileReporter, this is the file name.
        """
        try:
            path = self._parameters.get_params()["stdout"]
            if not os.path.exists(path):
                raise FileNotFoundError(f"{path} does not exist")
        except KeyError:
            path = os.getcwd()

        if rn is None:
            rn = "NA"

        return os.path.join(path, f"run_{rn}_{list(run.get_args().values())}.out")


class ModelProcess(threading.Thread):
    """A thread that runs a model process.

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
        """Executes the subprocess and yields the stdout line by line.

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
            # If the process was killed by a signal, ignore.
            if return_code != 2:
                raise RunnerError(f"Process exited with an error, check output. Return code: {return_code}")

    def run(self) -> None:
        """Main thread method to run the model process."""
        try:
            with self._reporter as f:
                for out in self.execute(self._command):
                    f.write(out)
        except Exception as e:
            self.exc = e

    def join(self) -> None:
        """Wait for the thread to finish.

        Returns:
            None

        Raises:
            Exception: If an exception was raised during the thread execution.
        """
        while self.is_alive():
            super().join(1)
            if self.exc is not None:
                raise self.exc


class Spawner:
    """Spawns the model processes."""

    def __init__(self) -> None:
        self.exc = None

    def run(self, labels, simulations, stop_event, async_runs) -> None:
        """Main loop to spawn the threads which run the processes."""
        label_itr = iter(labels)
        thread_queue = ThreadQueue(async_runs, stop_event)
        for sim in simulations:
            thread_queue.add(sim)

        try:
            for thread in thread_queue:
                thread_queue.start(thread)
                print(f"executing: {next(label_itr)}")
        except Exception as e:
            self.exc = e


class Runner:
    """The Runner is responsible for queueing and running the model/s.
    Runs are staged to the runner then executed when run is called.
    Parameters are passed to the runner to config the runner.

    Parameters:
        parameters (Parameters): The parameters of the model.
        *args (Runner | None): Variable number of runners to add to this runner.
        A runner can inherit runs from other runners, if required.
    """

    def __init__(self, parameters: Parameters, *args: "Runner") -> None:
        self._stop_event = threading.Event()
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

    def __iter__(self) -> "Runner":
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

    def run(self, *run_numbers: list[str]) -> None:
        """Run all the staged runs.

        Args:
            *run_numbers (str/s): Variable number of run numbers to execute.
            If there is only one model, no run number is required.
        """
        if self._stop_event.is_set():
            self._stop_event.clear()

        spawner = Spawner()
        thread = threading.Thread(target=spawner.run, args=(*self.arguments(*run_numbers),))
        thread.start()

        # Block until all runs are complete.
        while thread.is_alive():
            try:
                thread.join(1)
            except KeyboardInterrupt:
                self.stop()

        if spawner.exc is not None:
            raise spawner.exc
        print("---- ALL RUNS COMPLETE ----")

    def arguments(self, *run_numbers: list[str]) -> None:
        """Returns all the parameters required to run the models."""
        # Get flags from parameters, or use default
        try:
            flags = self._parameters.get_params()["flags"]
        except KeyError:
            flags = None

        # Get the number of async runs from parameters, or use default
        try:
            async_runs = self._parameters.get_params()["async_runs"]
        except KeyError:
            async_runs = 1

        # Deal with the run numbers.
        if len(run_numbers) == 0:
            run_numbers = [None]

        for rn in run_numbers:
            if rn is not None and not isinstance(rn, str):
                raise RunnerError("run number must be a string")

        # Get all the model processes and their labels which are to be run.
        simulations = []
        labels = []
        for run in self:
            for rn in run_numbers:
                command = self._build_command(self._parameters, run, flags, rn)
                reporter = self._reporter(self._parameters, run, rn)
                model_proc = ModelProcess(command, reporter)
                labels.append(f"{run}_{rn}")
                simulations.append(model_proc)

        return labels, simulations, self._stop_event, async_runs

    def stage(self, run: Run | list[Run]) -> None:
        """Adds a run/s to the list of runs for this model runner.

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
            raise RunnerError("run must be an instance of Run class or a list of Run objects")

        for r in run:
            self._stage_one(r)

    def _stage_one(self, run: Run) -> None:
        """Adds a run to the list of runs for this model runner.

        Args:
            run (Run): The run to be added.

        Raises:
            RunnerError: If the provided run is not an instance of the Run class.
            RunnerError: If the run arguments do not match the required arguments.

        Returns:
            None
        """
        if not isinstance(run, Run):
            raise RunnerError("run must be an instance of Run class")

        run_args: set = set(run.get_args().keys())
        req_args: set = set(self._parameters.get_run_args())

        if run_args != req_args:
            raise RunnerError(f"run arguments: {run_args}, do not match required arguments: {req_args}")

        if run not in self._runs:
            self._runs.append(run)

    def get_runs(self, *args: str, any=True):
        """Retrieves a list of runs based on the provided arguments.

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
        """Removes the provided runs from the staged runs.

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
                raise RunnerError(f"{run} - is not an instances of Run class")
            if run in self._runs:
                self._runs.remove(run)

    def stop(self) -> None:
        """Stops all models, gracefully.

        Returns:
            None
        """
        self._stop_event.set()

    def pause(self) -> None:
        """Pauses all running models.

        Returns:
            None

        Raises:
            NotImplementedError: If the method is not implemented.
        """
        raise NotImplementedError("pause is not implemented")

    def resume(self) -> None:
        """Resumes all paused models.

        Returns:
            None

        Raises:
            NotImplementedError: If the method is not implemented.
        """
        raise NotImplementedError("resume is not implemented")

    def _signal_handler(self, signal, frame):
        """Handler for the keyboard interrupt signal."""
        self.stop()

    abc.abstractmethod

    def _build_command(self, parameters: Parameters, run: Run, *flags: list[str]) -> list[str]:
        """Build the command string to pass to subprocess.run(), this will be model dependent."""
        pass
