import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class CorpusTests(unittest.TestCase):
    def test_source_integrity_and_reading_coverage(self):
        catalog = json.loads((ROOT/'docs/data/catalog.json').read_text())
        self.assertEqual(len(catalog), 5)
        for b in catalog:
            source = (ROOT/'sources'/b['file']).read_bytes()
            self.assertEqual(hashlib.sha256(source).hexdigest(), b['sha256'])
            self.assertEqual(source, (ROOT/'docs/texts'/b['file']).read_bytes())
            data = json.loads((ROOT/'docs/data'/f"{b['id']}.json").read_text())
            blocks = [p for s in data['chapters'] for p in s['paragraphs']]
            self.assertEqual(len(blocks), len(set(p['id'] for p in blocks)))
            self.assertTrue(all(p['text'] for p in blocks))
            self.assertEqual(sum(len(p['text']) for p in blocks), b['characters'])
            self.assertTrue(all(p['text'] in source.decode('utf-8') for p in blocks))

    def test_complete_volumes(self):
        def titles(book):
            return [s['title'] for s in json.loads((ROOT/f'docs/data/{book}.json').read_text())['chapters']]
        self.assertEqual(len(titles('yulei')), 140)
        self.assertEqual(titles('yulei')[-1], '朱子語類卷第一百四十')
        self.assertEqual(sum(t.startswith('论语精义') for t in titles('jingyi')), 20)
        self.assertEqual(sum(t.startswith('孟子精义') for t in titles('jingyi')), 14)
        self.assertEqual(sum(t.startswith('卷') for t in titles('yishu')), 10)
        self.assertEqual(sum(t.startswith('卷') for t in titles('jijie')), 10)
        self.assertIn('大学章句', titles('sishu'))
        self.assertIn('中庸章句', titles('sishu'))
        self.assertTrue(any('尽心章句下' in t for t in titles('sishu')))
