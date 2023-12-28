import unittest
import modelrunner.core.runnerbase as mr

class TestParameters(unittest.TestCase):
    def setUp(self) -> None:
        return super().setUp()
    
    def test_parameters(self):
        # Implement the get_run_args method
        class Parameters(mr.Parameters):
            def get_run_args(self):
                return ['a', 'b', 'c']
        
        # Test basic creation
        p: mr.Parameters = Parameters(a=1, b=2, c=3)
        self.assertEqual(p.get_params(), {'a': 1, 'b': 2, 'c': 3})
        self.assertEqual(p.get_run_args(), ['a', 'b', 'c'])
        
        # Test cloning
        p_extend: mr.Parameters = Parameters(p)
        self.assertEqual(p_extend.get_params(), {'a': 1, 'b': 2, 'c': 3})
        self.assertEqual(p_extend.get_run_args(), ['a', 'b', 'c'])

        # Test extending
        p_extend: mr.Parameters = Parameters(p, d=4)
        try:
            self.assertEqual(p_extend.get_params(), {'a': 1, 'b': 2, 'c': 3})
            self.fail('Expected AssertionError')
        except AssertionError:
            pass
        self.assertEqual(p_extend.get_params(), {'a': 1, 'b': 2, 'c': 3, 'd': 4})
        self.assertEqual(p_extend.get_run_args(), ['a', 'b', 'c'])

        # Test extending with override
        p_extend: mr.Parameters = Parameters(p, a=4)
        self.assertEqual(p_extend.get_params(), {'a': 4, 'b': 2, 'c': 3})

class TestRun(unittest.TestCase):
    def setUp(self) -> None:
        return super().setUp()
    
    def test_run(self):
        # Test basic creation
        r: mr.Run = mr.Run(a=1, b=2, c=3)
        self.assertEqual(r.get_args(), {'a': 1, 'b': 2, 'c': 3})
        
        # Test cloning
        r_extend: mr.Run = mr.Run(r)
        self.assertEqual(r_extend.get_args(), {'a': 1, 'b': 2, 'c': 3})

        # Test extending
        r_extend: mr.Run = mr.Run(r, d=4)
        self.assertEqual(r_extend.get_args(), {'a': 1, 'b': 2, 'c': 3, 'd': 4})

        # Test extending with override
        r_extend: mr.Run = mr.Run(r, a=4)
        self.assertEqual(r_extend.get_args(), {'a': 4, 'b': 2, 'c': 3})


class TestRunner(unittest.TestCase):
    def setUp(self):
        class Parameters(mr.Parameters):
            def get_run_args(self):
                return ['a', 'b', 'c']
        self.parameters = Parameters(a=1, b=2, c=3)

        self.r1 = mr.Run(a=1, b=2, c=3)
        self.r2 = mr.Run(a=4, b=5, c=6)
        self.r3 = mr.Run(a=7, b=8, c=9)

    def test_runner_creation(self):
        # Test basic creation
        r: mr.Runner = mr.Runner(self.parameters)
        self.assertEqual(r._parameters, self.parameters)
        self.assertEqual(r._runs, [])

        # Test creation with multiple runners
        runner1 = mr.Runner(self.parameters)
        runner1.stage(self.r1)
        runner2 = mr.Runner(self.parameters)
        runner2.stage(self.r2)
        runner2.stage(self.r3)
        r: mr.Runner = mr.Runner(self.parameters, runner1, runner2)
        self.assertEqual(r._runs, [self.r1, self.r2, self.r3])

    def test_add_runs(self):
        # Test adding a single run
        r: mr.Runner = mr.Runner(self.parameters)
        r.stage(self.r1)
        self.assertEqual(r._runs, [self.r1])

        # Test adding multiple runs
        r: mr.Runner = mr.Runner(self.parameters)
        r.stage(self.r1)
        r.stage(self.r2)
        r.stage(self.r3)
        self.assertEqual(r._runs, [self.r1, self.r2, self.r3])

        # Test adding duplicate runs
        r: mr.Runner = mr.Runner(self.parameters)
        r.stage(self.r1)
        r.stage(self.r1)
        r.stage(self.r1)
        self.assertEqual(r._runs, [self.r1])

        # Test adding runs that are not Run objects
        r: mr.Runner = mr.Runner(self.parameters)
        try:
            r.stage('a')
            self.fail('Expected RunnerError')
        except mr.RunnerError:
            pass
        self.assertEqual(r._runs, [])

        # Test adding runs that don't match the parameters
        r: mr.Runner = mr.Runner(self.parameters)
        r.stage(self.r1)
        try:
            r.stage(mr.Run(a=1, b=2, c=3, d=4))
            self.fail('Expected RunnerError')
        except mr.RunnerError:
            pass
        self.assertEqual(r._runs, [self.r1])

    def test_runner_iter(self):
        # Test iterating over runs
        r: mr.Runner = mr.Runner(self.parameters)
        r.stage(self.r1)
        r.stage(self.r2)
        r.stage(self.r3)
        self.assertEqual(list(r), [self.r1, self.r2, self.r3])
        self.assertEqual(list(r), [self.r1, self.r2, self.r3])

    def test_get_runs(self):
        # Test getting runs
        r: mr.Runner = mr.Runner(self.parameters)
        r.stage(self.r1)
        r.stage(self.r2)
        r.stage(self.r3)
        self.assertEqual(r.get_runs(), [self.r1, self.r2, self.r3])

        # Test getting runs with a filter with any=True
        r: mr.Runner = mr.Runner(self.parameters)
        r.stage(self.r1)
        r.stage(self.r2)
        r.stage(self.r3)
        r4 = mr.Run(a=1, b=10, c=11)
        r.stage(r4)
        runs = r.get_runs(True, 1)
        self.assertEqual(runs, [self.r1, r4])

        # Test that adding more filters doesnt effect the return
        runs = r.get_runs(True, 1, 3)
        self.assertEqual(runs, [self.r1, r4])

        # Test that adding more filters gets the value 9
        runs = r.get_runs(True, 1, 3, 9)
        self.assertTrue(self.r1 in runs)
        self.assertTrue(self.r3 in runs)
        self.assertTrue(r4 in runs)

        # Test getting runs with a filter with any=False
        r: mr.Runner = mr.Runner(self.parameters)
        r.stage(self.r1)
        r.stage(self.r2)
        r.stage(self.r3)
        r4 = mr.Run(a=1, b=10, c=11)
        r.stage(r4)
        runs = r.get_runs(False, 1, 2)
        self.assertEqual(runs, [self.r1])

        # Test that value 10 only get r4
        runs = r.get_runs(False, 10)
        self.assertEqual(runs, [r4])

        # Test that value 15 gets nothing
        runs = r.get_runs(False, 15)
        self.assertEqual(runs, [])


    def test_remove_runs(self):
        # Test removing runs
        r: mr.Runner = mr.Runner(self.parameters)
        r.stage(self.r1)
        r.stage(self.r2)
        r.stage(self.r3)
        r.remove_runs([self.r1, self.r3])
        self.assertEqual(r._runs, [self.r2])

        # Test removing runs that don't exist
        r: mr.Runner = mr.Runner(self.parameters)
        r.stage(self.r1)
        r.stage(self.r2)
        r.stage(self.r3)
        r4 = mr.Run(a=1, b=10, c=11)
        r.remove_runs([self.r1, self.r3, r4])
        self.assertEqual(r._runs, [self.r2])

        # Test removing runs that don't match the parameters
        r: mr.Runner = mr.Runner(self.parameters)
        r.stage(self.r1)
        r.stage(self.r2)
        r.stage(self.r3)
        r.remove_runs(mr.Run(a=1, b=2, c=3, d=4))
        self.assertEqual(r._runs, [self.r1, self.r2, self.r3])

        # Test removing runs that are not Run objects
        r: mr.Runner = mr.Runner(self.parameters)
        r.stage(self.r1)
        r.stage(self.r2)
        r.stage(self.r3)
        try:
            r.remove_runs(['a'])
            self.fail('Expected RunnerError')
        except mr.RunnerError:
            pass
        self.assertEqual(r._runs, [self.r1, self.r2, self.r3])

    def test_remove_using_filter(self):
        # Test removing runs with a filter with any=True
        r: mr.Runner = mr.Runner(self.parameters)
        r.stage(self.r1)
        r.stage(self.r2)
        r.stage(self.r3)
        r4 = mr.Run(a=1, b=10, c=11)
        r.stage(r4)

        # This will return r1 and r4
        to_remove = r.get_runs(True, 1)
        r.remove_runs(to_remove)
        self.assertEqual(r._runs, [self.r2, self.r3])

if __name__ == '__main__':
    unittest.main()