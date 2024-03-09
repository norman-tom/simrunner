import unittest
import sys
import threading
import time
import os
import modelrunner.core.runnerbase as mr

class TestTaskQueue(unittest.TestCase):
    def setUp(self) -> None:
        self.queue = mr.TaskQueue(2)
    
    def test_add_too_many(self):
        thread1 = threading.Thread(target=time.sleep, args=(0.1,))
        thread2 = threading.Thread(target=time.sleep, args=(0.1,))
        thread3 = threading.Thread(target=time.sleep, args=(0.1,))
        self.queue.add(thread1)
        self.queue.add(thread2)
        with self.assertRaises(mr.RunnerError):
            self.queue.add(thread3)

class TestThreadQueue(unittest.TestCase):
    def setUp(self):
        self.queue = mr.ThreadQueue(2)

    def test_add_remove(self):
        thread = threading.Thread(target=time.sleep, args=(0.1,))
        self.queue.add(thread)
        self.assertEqual(len(self.queue._tasks), 1)
        self.queue.remove(thread)
        self.assertEqual(len(self.queue._tasks), 0)

    def test_full(self):
        thread1 = threading.Thread(target=time.sleep, args=(0.1,))
        thread2 = threading.Thread(target=time.sleep, args=(0.1,))
        self.queue.add(thread1)
        self.queue.add(thread2)
        self.assertTrue(self.queue.full())

    def test_wait(self):
        thread1 = threading.Thread(target=time.sleep, args=(0.1,))
        thread2 = threading.Thread(target=time.sleep, args=(0.1,))
        self.queue.add(thread1)
        self.queue.add(thread2)
        self.queue.wait()
        self.assertFalse(self.queue.full())

    def test_wait_all(self):
        thread1 = threading.Thread(target=time.sleep, args=(0.1,))
        thread2 = threading.Thread(target=time.sleep, args=(0.1,))
        self.queue.add(thread1)
        self.queue.add(thread2)
        self.queue.wait_all()
        self.assertEqual(len(self.queue._threads), 0)

class TestModelProcess(unittest.TestCase):
    def test_model_process(self):
        process_args = ['python', './tests/stubs/process.py', '0.1']
        process = mr.ModelProcess(process_args, mr.Reporter())
        process.start()
        self.assertTrue(process.is_alive())
        process.join()
        self.assertFalse(process.is_alive())

class TestThreadedProcess(unittest.TestCase):
    def test_threaded_process(self):
        process_args = ['python', './tests/stubs/process.py', '0.1']
        thread_queue = mr.ThreadQueue(2)
        thread_queue.add(mr.ModelProcess(process_args, mr.Reporter()))
        thread_queue.add(mr.ModelProcess(process_args, mr.Reporter()))
        self.assertEqual(len(thread_queue._tasks), 2)
        thread_queue.wait_all()
        self.assertEqual(len(thread_queue._threads), 0)

    def test_waiting_on_finish(self):
        process_args = ['python', './tests/stubs/process.py', '0.1']
        thread_queue = mr.ThreadQueue(2)
        thread_queue.add(mr.ModelProcess(process_args, mr.Reporter()))
        thread_queue.add(mr.ModelProcess(process_args, mr.Reporter()))
        for _ in range(5):
            thread_queue.wait()
            thread_queue.add(mr.ModelProcess(process_args, sys.stdout))

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
        runs = r.get_runs(1, 2, any=False)
        self.assertEqual(runs, [self.r1])

        # Test that value 10 only get r4
        runs = r.get_runs(10, any=False)
        self.assertEqual(runs, [r4])

        # Test that value 15 gets nothing
        runs = r.get_runs(15, any=False)
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

    def test_runner_run(self): 
        # setup parameters
        class MyRunner(mr.Runner):
            def _build_command(self, parameters: mr.Parameters, run: mr.Run, *flags: list[str]) -> list[str]:
                return ['python', './tests/stubs/writing_process.py', '0.1']
            
        class MyParameters(mr.Parameters):
            def get_run_args(self):
                return ['a', 'b', 'c']
            
        start = time.time()
        
        parameters = MyParameters(async_runs=2)
        runner = MyRunner(parameters)
        run1 = mr.Run(a=1, b=2, c=3)
        run2 = mr.Run(a=4, b=5, c=6)
        run3 = mr.Run(a=7, b=8, c=9)
        run4 = mr.Run(a=10, b=11, c=12)
        run5 = mr.Run(a=13, b=14, c=15)
        runner.stage(run1)
        runner.stage(run2)
        runner.stage(run3)
        runner.stage(run4)
        runner.stage(run5)
        runner.run()

        if time.time() - start < 0.3:
            self.fail('Expected run to take more than 0.3 seconds')

    def test_runner_indexing(self):
        parameters = self.parameters
        runner = mr.Runner(parameters)
        run1 = mr.Run(a=1, b=2, c=3)
        run2 = mr.Run(a=4, b=5, c=6)
        run3 = mr.Run(a=7, b=8, c=9)
        runner.stage(run1)
        runner.stage(run2)
        runner.stage(run3)
        self.assertEqual(runner[0], run1)
        self.assertEqual(runner[1], run2)
        self.assertEqual(runner[2], run3)
        self.assertEqual(runner[0:2], [run1, run2])
    
    def test_stdout(self):
        # setup parameters
        class MyRunner(mr.Runner):
            def _build_command(self, parameters: mr.Parameters, run: mr.Run, *flags: list[str]) -> list[str]:
                return ['python', './tests/stubs/writing_process.py', '0.01']
            
        class MyParameters(mr.Parameters):
            def get_run_args(self):
                return ['a', 'b', 'c']
            
        parameters = MyParameters(async_runs=2, stdout=r'./tests/stdout')
        runner = MyRunner(parameters)

        # Remove all the files in the directory
        folder_path = 'tests/stdout'
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)

        run1 = mr.Run(a=1, b=2, c=3)
        run2 = mr.Run(a=4, b=5, c=6)
        runner.stage(run1)
        runner.stage(run2)
        runner.run()

        # Check if the file exists
        for filename in ['run_NA_[1, 2, 3].out', 'run_NA_[4, 5, 6].out']:
            file_path = os.path.join(folder_path, filename)
            if os.path.isfile(file_path):
                self.assertTrue(True)
            else:
                self.fail('Expected file to be created')

        # Remove files that start with "run_NA_"
        folder_path = os.getcwd()
        for filename in os.listdir(folder_path):
            if filename.startswith('run_NA_['):
                file_path = os.path.join(folder_path, filename)
                os.remove(file_path)

        # Update the parameters to not use a stdout folder
        parameters = MyParameters(async_runs=2)
        runner.__dict__['_parameters'] = parameters
        runner.run()

        # Check if the file exists in the correct location
        for filename in ['run_NA_[1, 2, 3].out', 'run_NA_[4, 5, 6].out']:
            file_path = os.path.join(folder_path, filename)
            if os.path.isfile(file_path):
                self.assertTrue(True)
                os.remove(file_path) # Clean up root folder
            else:
                self.fail('Expected file to be created')

        parameters = MyParameters(async_runs=2, stdout=r'./tests/stdout/noexist')
        runner.__dict__['_parameters'] = parameters
        try:
            runner.run()
            self.fail('Expected FileNotFoundError')
        except FileNotFoundError:
            pass
        

if __name__ == '__main__':
    unittest.main()