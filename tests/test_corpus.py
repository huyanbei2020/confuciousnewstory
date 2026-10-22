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
            edits = {(e['book'], e['paragraph']): e for e in json.loads((ROOT/'sources/editorial.json').read_text())['edits']}
            for p in blocks:
                edit = edits.get((b['id'], p['id']))
                self.assertIn(edit['before'] if edit else p['text'], source.decode('utf-8'))
                if edit:
                    self.assertEqual(p['text'], edit['text'])
                    self.assertEqual(p['reference'], edit['reference'])

    def test_complete_volumes(self):
        def titles(book):
            return [s['title'] for s in json.loads((ROOT/f'docs/data/{book}.json').read_text())['chapters']]
        self.assertEqual(len(titles('yulei')), 140)
        self.assertEqual(titles('yulei')[-1], '朱子語類卷第一百四十')
        self.assertEqual(sum(t.startswith('论语精义') for t in titles('jingyi')), 20)
        self.assertEqual(sum(t.startswith('孟子精义') for t in titles('jingyi')), 14)
        self.assertEqual(sum(t.startswith('卷') for t in titles('yishu')), 10)
        self.assertEqual(sum(t.startswith('卷') for t in titles('zhengyi')), 24)
        self.assertEqual(len(titles('zhengyi')), 27)
        self.assertIn('附録·鄭玄論語序逸文', titles('zhengyi'))
        self.assertEqual(titles('zhengyi')[-1], '劉恭冕後敍')
        self.assertIn('大学章句', titles('sishu'))
        self.assertIn('中庸章句', titles('sishu'))
        self.assertTrue(any('尽心章句下' in t for t in titles('sishu')))

    def test_replacement_preserves_annotations_and_removes_old_book(self):
        import re
        import sys
        sys.path.insert(0, str(ROOT / 'scripts'))
        from build import sections
        catalog = json.loads((ROOT/'docs/data/catalog.json').read_text())
        self.assertIn('zhengyi', [b['id'] for b in catalog])
        self.assertNotIn('jijie', [b['id'] for b in catalog])
        for filename in ('sources/jijie.md', 'docs/texts/jijie.md', 'docs/data/jijie.json'):
            self.assertFalse((ROOT/filename).exists())
        raw = (ROOT/'sources/zhengyi.md').read_text()
        data = json.loads((ROOT/'docs/data/zhengyi.json').read_text())
        source_sections = sections(raw, 'zhengyi')
        self.assertEqual(len(source_sections), len(data['chapters']))
        for (_, body), chapter in zip(source_sections, data['chapters']):
            lines = [re.sub(r'字數：\d+，最後更新時間：.*$', '', line.strip()) for line in body.splitlines()]
            expected = ''.join(line for line in lines if not (line.startswith('**〔') and line.endswith('〕**')))
            actual = ''.join(p['text'] for p in chapter['paragraphs'])
            self.assertEqual(actual, expected)
        paragraphs = [p['text'] for c in data['chapters'] for p in c['paragraphs']]
        self.assertTrue(any(p.startswith('【〔注〕馬曰') for p in paragraphs))
        self.assertFalse(any('最後更新時間' in p for p in paragraphs))

    def test_editorial_changes_preserve_all_original_characters(self):
        import unicodedata
        def lexical(text):
            return ''.join(c for c in text if not c.isspace() and not unicodedata.category(c).startswith('P'))
        edits = json.loads((ROOT/'sources/editorial.json').read_text())['edits']
        self.assertTrue(edits)
        self.assertEqual(len(edits),len({(e['book'],e['paragraph']) for e in edits}))
        for e in edits:
            self.assertEqual(hashlib.sha256(e['before'].encode()).hexdigest(),e['before_sha256'])
            self.assertEqual(lexical(e['before']),lexical(e['text']))
            self.assertTrue(e['reference'].startswith('https://www.shidianguji.com/book/SK0542/chapter/'))
            self.assertEqual(e['layer'],'经文' if e['paragraph'] in ('p15','p22') else '诸家解说')
