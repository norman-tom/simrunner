from ..core import runnerbase
import os
import re

class Parameters(runnerbase.Parameters):
    def get_run_args(self):
        """
        Get the required arguments to make a vaild run.
        """

        tcf = self.get_tcf()
        tcf_file = os.path.basename(tcf)

        return self.__get_argument_tokens(tcf_file)

    def get_tcf(self) -> str:
        """
        Return the tuflow control file.
        """

        root_path = os.path.realpath(self.root)

        tcf_files = []
        for root, dirs, files in os.walk(root_path):
            for file in files:
                if file.endswith(".tcf"):
                    tcf_files.append(os.path.join(root, file))
        
        if len(tcf_files) == 0:
            raise FileNotFoundError(f"No .tcf files found in {self.root}.")
        
        if len(tcf_files) > 1:
            raise FileNotFoundError(f"Multiple .tcf files found {self.root}.")
        
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

        ret = ['-b']
        for k, v in self.get_args().items():
            ret.append(f"-{k}")
            ret.append(f"{v}")

        return ret


class Runner(runnerbase.Runner):
    def _build_command(self, parameters: Parameters, run: Run) -> list[str]:
        """
        Build the command string to pass to subprocess.run(), this will be model dependent.
        """
        return [parameters.executable(), *run.run_args(), parameters.get_tcf()]