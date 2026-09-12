from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import validate, engine_path


def run(seed, border=512, version='1.21'):
    return subprocess.run([str(engine_path()), str(seed), str(border), version], capture_output=True, text=True, timeout=120)


class ExporterTests(unittest.TestCase):
    def test_precision(self):
        self.assertEqual(validate('9223372036854775807', '15900')[0], '9223372036854775807')
        self.assertEqual(validate('-9223372036854775808', '1')[0], '-9223372036854775808')
        for bad in ('9223372036854775808', '-9223372036854775809', '1.2', '', '1e10'):
            with self.assertRaises(ValueError):
                validate(bad, '15900')

    def test_invalid_engine_arguments(self):
        for args in [('9223372036854775808', 100, '1.21'), ('1x', 100, '1.21'), (1, 15901, '1.21'), (1, 0, '1.21'), (1, 100, 'bedrock')]:
            result = run(*args)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(result.stdout)

    def test_small_and_empty(self):
        for seed in (0, -1, -9223372036854775808, 9223372036854775807):
            result = run(seed, 1)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('PROGRESS 100', result.stderr)

    def test_format_unique_boundary_and_determinism(self):
        result = run(12345, 3000)
        self.assertEqual(result.returncode, 0, result.stderr)
        points = [tuple(map(int, part.split())) for part in result.stdout.strip().split(';') if part.strip()]
        self.assertTrue(points, 'fixture must exercise non-empty export')
        self.assertEqual(len(points), len(set(points)))
        self.assertTrue(all(len(p)==2 and max(map(abs,p))<=3000 for p in points))
        self.assertEqual(run(12345,3000).stdout, result.stdout)
        subset = run(12345,1000)
        small = {tuple(map(int,p.split())) for p in subset.stdout.split(';') if p.strip()}
        self.assertEqual(small, {p for p in points if max(map(abs,p))<=1000})


if __name__ == '__main__':
    unittest.main()
