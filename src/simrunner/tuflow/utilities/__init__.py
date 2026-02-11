from .raster import ParameterMap, RasterProcessor, UtilityConfig
import glob
import os
from ...core.runnerbase import Runner

__all__ = [
    "UtilityConfig",
    "RasterProcessor",
    "ParameterMap"
]

def run(runner: Runner, rn: str, skip=False):
    if skip: return
    print("Staged runs:")
    print(*runner.get_runs(), sep='\n')
    print()
    response = input("Do you want to continue with the actual run? (y/n): ").lower().strip()
    if response in ['y', 'yes']:
        print("Proceeding with the run...")
        files = glob.glob(r'.\stdout\*')
        for f in files: 
            os.remove(f)
        runner.run(rn)
    else:
        print("Run cancelled.")