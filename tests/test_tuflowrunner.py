import unittest
import os
import simrunner.tuflow as mr

class TestParameters(unittest.TestCase):
    def setUp(self) -> None:
        return super().setUp()
    
    def test_get_tcf(self):
        # Test basic creation
        p: mr.Parameters = mr.Parameters(root=r"tests\data\tuflow\one_tcf", engine=None, version=None, exec_path=None)
        test_path = os.path.realpath(r"tests\data\tuflow\one_tcf\model_~s1~_~e1~_~e2~.tcf")
        self.assertEqual(p.get_tcf(""), test_path)
        
        # Test with multiple tcf files
        p: mr.Parameters = mr.Parameters(root=r"tests\data\tuflow\multi_tcf", engine=None, version=None, exec_path=None)
        try:
            p.get_tcf("")
            self.fail('Expected FileNotFoundError')
        except FileNotFoundError:
            pass
        
        # Test with no tcf files
        p: mr.Parameters = mr.Parameters(root=r"tests\data\tuflow\no_tcf", engine=None, version=None, exec_path=None)
        try:
            p.get_tcf("")
            self.fail('Expected FileNotFoundError')
        except FileNotFoundError:
            pass

    def test_not_all_required(self):
        # Test with missing parameters
        try:
            p: mr.Parameters = mr.Parameters(root=r"tests\data\tuflow\one_tcf")
            self.fail('Expected ValueError')
        except ValueError:
            pass

    def test_get_executable(self):
        # Test basic creation
        p: mr.Parameters = mr.Parameters(exec_path=r"tests\data\tuflow\executables",
                                         root=r"tests\data\tuflow\one_tcf",
                                         version=r"2020-10-AD",
                                         engine=r"DP")
        test_path = os.path.realpath(r"tests\data\tuflow\executables\2020-10-AD\TUFLOW_iDP_w64.exe")
        self.assertEqual(p.executable(), test_path)
        
        # Test with invalid engine
        p: mr.Parameters = mr.Parameters(p, engine=r"invalid")
        try:
            p.executable()
            self.fail('Expected ValueError')
        except ValueError:
            pass

    def test_get_argument_tokes(self):
        # Test basic creation
        p: mr.Parameters = mr.Parameters(exec_path=r"tests\data\tuflow\executables",
                                    root=r"tests\data\tuflow\one_tcf",
                                    version=r"2020-10-AD",
                                    engine=r"DP")
        test_tokens = ["s1", "e1", "e2"]
        self.assertEqual(p.get_run_args(), test_tokens)

    def test_group_id(self):
        # Test basic creation
        p: mr.Parameters = mr.Parameters(exec_path=r"tests\data\tuflow\executables",
                                    root=r"tests\data\tuflow\group_tcf",
                                    version=r"2020-10-AD",
                                    engine=r"DP",
                                    group="MY_PRJ")
        self.assertEqual(p._find_tcfs(), [os.path.realpath(r"tests\data\tuflow\group_tcf\MY_PRJ_~s1~_~e1~_~e2~_~e3~_01.tcf"),
                                          os.path.realpath(r"tests\data\tuflow\group_tcf\MY_PRJ_~s1~_~e1~_~e2~_~e3~_02.tcf")])
        
        p: mr.Parameters = mr.Parameters(exec_path=r"tests\data\tuflow\executables",
                                    root=r"tests\data\tuflow\group_tcf",
                                    version=r"2020-10-AD",
                                    engine=r"DP",
                                    group="THERE_PRJ")
        self.assertEqual(p._find_tcfs(), [os.path.realpath(r"tests\data\tuflow\group_tcf\THERE_PRJ_~s1~_~e1~_~e2~.tcf")])

class TestRun(unittest.TestCase):
    def setUp(self) -> None:
        return super().setUp()
    
    def test_get_run_args(self):
        # Test basic creation
        r: mr.Run = mr.Run(a='1', b='2', c='3')
        test_tokens = ["-a", "1", "-b", "2", "-c", "3"]
        self.assertEqual(r.run_args(), test_tokens)

class TestRunner(unittest.TestCase):
    def setUp(self) -> None:
        return super().setUp()
    
    def test_build_command(self):
        # Test basic creation
        p: mr.Parameters = mr.Parameters(exec_path=r"tests\data\tuflow\executables",
                                         root=r"tests\data\tuflow\one_tcf",
                                         version=r"2020-10-AD",
                                         engine=r"DP")
        r: mr.Run = mr.Run(s1='1', e1='2', e2='3')
        runner = mr.Runner(p)
        runner.stage(r)
        
        test_tokens = [os.path.realpath(r"tests\data\tuflow\executables\2020-10-AD\TUFLOW_iDP_w64.exe"),
                       "-b", "-s1", "1", "-e1", "2", "-e2", "3",
                       os.path.realpath(r"tests\data\tuflow\one_tcf\model_~s1~_~e1~_~e2~.tcf")]
        
        self.assertEqual(runner._build_command(p, r, ["-b"], ""), test_tokens)

    def test_real(self):
        p: mr.Parameters = mr.Parameters(exec_path=r"C:\Program Files\TUFLOW",
                                         root=r"tests\data\tuflow\one_tcf",
                                         version=r"2020-10-AD",
                                         engine=r"DP")
        r: mr.Run = mr.Run(s1='DES', e1='M60', e2='CC')
        runner = mr.Runner(p)
        runner.stage(r)
        runner.run()