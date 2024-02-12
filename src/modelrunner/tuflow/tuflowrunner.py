from modelrunner.core.runnerbase import Parameters
from ..core import runnerbase
import os
import re

class Parameters(runnerbase.Parameters):
    def __init__(self, clone: Parameters = None, **kwargs):
        if 'flags' in kwargs:
            if not isinstance(kwargs['flags'], list):
                raise ValueError("flags must be a list.")
        
        super().__init__(clone, **kwargs)
        self._run_args = None
            
    def get_run_args(self) -> list[str]:
        """
        Get the required arguments to make a vaild run.
        """

        if self._run_args is None:
            tcf = self._find_tcfs()

            if tcf is None:
                raise FileNotFoundError(f"No .tcf files found in {self.root}.")
            
            tcf_file = os.path.basename(tcf[0])
            self._run_args = self.__get_argument_tokens(tcf_file)

        return self._run_args

    def _find_tcfs(self) -> list[str] | None:
        """
        Find all the tcf files in the root directory.

        Returns:
            list[str]: A list of all the tcf files found. None if no tcf files found.
        """

        root_path = os.path.realpath(self.root)

        tcf_files = []
        for root, _, files in os.walk(root_path):
            for file in files:
                if file.endswith(".tcf"):
                    tcf_files.append(os.path.join(root, file))
        
        if len(tcf_files) > 0:
            return tcf_files
        else:
            return None
    
    def get_tcf(self, run_number: str) -> str:
        """
        Return the tuflow control file.
        """
        tcf_files = self._find_tcfs()
        
        if tcf_files is None:
            raise FileNotFoundError(f"No .tcf files found in {self.root}.")
        
        if len(tcf_files) > 1:
            # if there are more than one tcf, we need to match on the run number.
            # we are going to assume run numbers are always at the end of the file name and lead with an underscore.

            if run_number is None:
                raise ValueError(f"Multiple .tcf files found in {self.root}. Must specify run number.")

            pattern = f"_{run_number}\.tcf$"
            matches = [tcf for tcf in tcf_files if re.search(pattern, tcf)]

            if len(matches) == 0:
                raise FileNotFoundError(f"No .tcf files found in {self.root} with run number {run_number}.")
            
            if len(matches) > 1:
                raise FileNotFoundError(f"Multiple .tcf files found in {self.root} with run number {run_number}.")
            
            tcf_files = matches
        
        return tcf_files[0]
    
    def executable(self) -> str:
        """
        Build the path to the correct executable.
        """

        req_parameters = {"exec_path", "root", "version", "engine"}
        
        if not req_parameters.issubset(self.get_params()):
            raise ValueError("Missing required parameters.")
        
        engine = self.engine.upper()
        if engine not in {"SP", "DP"}:
            raise ValueError("Invalid engine. must be 'DP' or 'SP'.")
        
        engine = f"TUFLOW_i{engine}_w64.exe"

        exec_path = os.path.realpath(self.exec_path)

        return os.path.join(exec_path, self.version, engine)
    
    def __get_argument_tokens(self, tcf_file: str) -> list[str]:
        """
        Parse the tcf_file to get the argument tokens.
        """

        # Extract the argument tokens using regex
        pattern = r"~([^~]+)~"
        argument_tokens = re.findall(pattern, tcf_file)

        return argument_tokens


class Run(runnerbase.Run):
    def __init__(self, clone: 'Run'=None, **kwargs) -> list[str]:
        super().__init__(clone, **kwargs)

    def run_args(self) -> list[str]:
        """
        Get the arguments.
        """

        ret = []
        for k, v in self.get_args().items():
            ret.append(f"-{k}")
            ret.append(f"{v}")

        return ret


class Runner(runnerbase.Runner):
    def _build_command(self, parameters: Parameters, run: Run, flags: list[str], run_number: str) -> list[str]:
        """
        Build the command string to pass to subprocess.run(), this will be model dependent.
        """
        if not flags:
            flags = [""]

        return [parameters.executable(), *flags, *run.run_args(), parameters.get_tcf(run_number)]