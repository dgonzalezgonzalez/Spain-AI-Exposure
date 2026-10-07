import tempfile
from pathlib import Path
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from master import table_cells, safe_destination


class ReplicationTests(unittest.TestCase):
    def test_comparison_ignores_comments_and_layout_but_checks_stars(self):
        with tempfile.TemporaryDirectory() as folder:
            a, b = Path(folder)/'a.tex', Path(folder)/'b.tex'
            a.write_text(r'\begin{tabular}{lc}'+'\n'+r'\cmidrule{1-2}'+'\n'+r'Estimate & 0.012$^{**}$ \\'+'\n'+r'% Old result & 9.123 \\'+'\n'+r'N & 31,626 \\'+'\n'+r'\end{tabular}')
            b.write_text(r'\begin{tabular}{lc}'+'\n'+r'Estimate & 0.012$^{**}$ \\'+'\n'+r'N & 31626 \\'+'\n'+r'\end{tabular}')
            self.assertEqual(table_cells(a), table_cells(b))
            b.write_text(b.read_text().replace('**','*'))
            self.assertNotEqual(table_cells(a), table_cells(b))

    def test_archive_paths_cannot_escape_destination(self):
        root = Path(tempfile.gettempdir())/'replication'
        with self.assertRaises(ValueError): safe_destination(root, '../outside')
        self.assertEqual(safe_destination(root, 'data/panel.csv'), root.resolve()/'data/panel.csv')


if __name__ == '__main__': unittest.main()
