import os
import unittest

from simrunner.tuflow import ParameterMap, RasterProcessor, Run, UtilityConfig


class TestUtilityFunctions(unittest.TestCase):
    def setUp(self):
        self.runs = [
            Run(**kwargs)
            for kwargs in [
                {"s1": "exg", "s2": "nb", "e1": "1p", "e2": "0270min", "e3": "tp02", "e4": "5pSS", "e5": "2024"},
                {"s1": "exg", "s2": "nb", "e1": "1p", "e2": "1440min", "e3": "tp07", "e4": "5pSS", "e5": "2024"},
                {"s1": "mtg", "s2": "nb", "e1": "1p", "e2": "0270min", "e3": "tp02", "e4": "5pSS", "e5": "2024"},
                {"s1": "mtg", "s2": "nb", "e1": "1p", "e2": "1440min", "e3": "tp07", "e4": "5pSS", "e5": "2024"},
            ]
        ]

        root = os.path.dirname(os.path.abspath(__file__))
        self.config = UtilityConfig(
            tcf_template="24013_~s1~_~s2~_~e1~_~e2~_~e3~_~e4~_~e5~",
            result_path_template=f"{root}\\data\\24013\\<<~s1~>>\\<<~s2~>>\\<<~e1~>>\\<<~e2~>>\\2D\\grids",
            output_template=f"{root}\\data\\24013\\processed\\<<~s1~>>\\<<~s2~>>\\<<~e1~>>",
            parameter_map=ParameterMap('e1', 'e2', 'e3')
        )

    def test_aggregate_tp(self):
        processor = RasterProcessor(self.config)
        processor.aggregate_tps(self.runs)

    def test_aggregate_duration(self):
        processor = RasterProcessor(self.config)
        processor.aggregate_duration(self.runs)

    def test_afflux(self):
        processor = RasterProcessor(self.config)
        processor.elevation_afflux(self.runs[:2], self.runs[2:])

    def test_afflux_with_parameter(self):
        processor = RasterProcessor(self.config)
        processor.elevation_afflux(self.runs[:2], self.runs[2:], 's1')

        with self.assertRaises(ValueError):
            processor.elevation_afflux(self.runs[:2], self.runs[2:], 'e2')
