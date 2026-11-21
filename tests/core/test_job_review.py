"""The worker preserves existing module flags and exposes M1 rule evidence."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from analysis.engine import analyze
from api import jobs, store


class ReviewIntegration(unittest.TestCase):
    def test_build_preserves_m2_review_and_keeps_independent_semantic_result(self):
        with TemporaryDirectory() as directory, patch.object(store, 'STATE', Path(directory)):
            store.init()
            m1 = {'id':'m1','module':'M1','title':'Materiał','description':'Partnerem odcinka jest XTB.',
                  'url':'https://example.org/a'}
            m2 = {'id':'m2','module':'M2','title':'Oferta','description':'Informacja.','url':'https://example.org/oferta'}
            def findings(cap):
                result = analyze(cap)
                if cap['id'] == 'm2':
                    result['reviewSuggestion'] = {'state':'review','source':'m2-evidence'}
                return result
            with patch('collectors.discovery.discover', return_value={'creators':[],'captures':[m1,m2],'sources':[]}), \
                 patch('collectors.m2_archive.staged_captures', return_value=([], [], [])), \
                 patch('analysis.engine.demo_captures', return_value=[]), \
                 patch('analysis.engine.analyze', side_effect=findings), \
                 patch('analysis.semantic.suggest', return_value={'status':'unavailable'}):
                records, _, _ = jobs.build({'mode':'replay'})
            first, second = (finding for _, finding in records)
            self.assertEqual(first['reviewSuggestion']['state'], 'review')
            self.assertEqual(first['reviewSuggestion']['source'], 'rules')
            self.assertEqual(first['semantic']['status'], 'unavailable')
            self.assertEqual(second['reviewSuggestion'], {'state':'review','source':'m2-evidence'})
