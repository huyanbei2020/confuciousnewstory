"""Build portable, source-traceable reading data with Python's standard library."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/data'

def sections(raw, book):
    if book in ('yishu', 'zhengyi', 'yulei'):
        parts = re.split(r'(?m)^## (.+)\n', raw)
        return [(parts[i], parts[i+1]) for i in range(1, len(parts), 2)
                if parts[i] not in ('整理说明', '题名')]
    result, title, buf, seen = [], '提要与序' if book == 'jingyi' else '原书目录', [], set()
    for line in raw.splitlines():
        clean = line.strip()
        if book == 'jingyi':
            key = clean.replace('巻', '卷')
            heading = bool(re.fullmatch(r'(?:论语|孟子)精义卷[一二三四五六七八九十]+[上下]?', key))
            if heading and key in seen:
                continue  # repeated end-of-volume running titles, retained in source download
            if heading:
                seen.add(key)
            if clean.startswith('<经部,'):
                continue
        else:
            heading = bool(re.fullmatch(r'卷[一二三四五六七八九十]+\s+[^卷]+', clean)) or clean in (
                '大学章句序', '大学章句', '中庸章句序', '中庸章句', '论语序说', '读论语孟子法', '孟子序说') or clean.startswith(('附录一', '附录二'))
            # The first 33 lines are the original table of contents.
            if '大学之书' not in '\n'.join(buf) and not result and clean != '大学章句序':
                heading = False
        if heading:
            if buf:
                result.append((title, '\n'.join(buf)))
            title, buf = clean, []
        else:
            buf.append(line)
    if buf:
        result.append((title, '\n'.join(buf)))
    return result

def blocks(text, book=None):
    layer, result = '', []
    for line in text.splitlines():
        line = line.strip()
        if book == 'zhengyi':
            # Remove the source website footer, preserving all preceding classical text.
            line = re.sub(r'字數：\d+，最後更新時間：.*$', '', line)
        if not line or re.fullmatch(r'PAGE\s+.*MERGEFORMAT.*', line):
            continue
        if (line.startswith('**〔') and line.endswith('〕**')) or (book != 'zhengyi' and line.startswith('【') and line.endswith('】')):
            layer = line.strip('*【】〔〕')
            continue
        # Bound DOM size without dropping or rewriting text; join fragments to reconstruct each line.
        while len(line) > 900:
            end = max(line.rfind('。', 400, 900), line.rfind('；', 400, 900))
            end = end + 1 if end >= 400 else 900
            result.append({'text': line[:end], 'layer': layer})
            line = line[end:]
        if line:
            result.append({'text': line, 'layer': layer})
    return result

def build():
    OUT.mkdir(parents=True, exist_ok=True)
    downloads = ROOT / 'docs/texts'
    downloads.mkdir(exist_ok=True)
    catalog = []
    editorial_path = ROOT / 'sources/editorial.json'
    edits = json.loads(editorial_path.read_text())['edits'] if editorial_path.exists() else []
    edit_index = {(e['book'], e['paragraph']): e for e in edits}
    applied = set()
    zhengyi_path = ROOT / 'sources/zhengyi-collation.json'
    zhengyi = json.loads(zhengyi_path.read_text()) if zhengyi_path.exists() else None
    zhengyi_index = {p['paragraph']: p for p in zhengyi['paragraphs']} if zhengyi else {}
    for source in json.loads((ROOT / 'sources/manifest.json').read_text()):
        data = (ROOT / 'sources' / source['file']).read_bytes()
        assert hashlib.sha256(data).hexdigest() == source['sha256'], source['id']
        if source['id'] == 'zhengyi' and zhengyi:
            assert hashlib.sha256(data).hexdigest() == zhengyi['source_sha256']
        (downloads / source['file']).write_bytes(data)
        chapters = []
        count = 0
        for title, body in sections(data.decode('utf-8-sig'), source['id']):
            paragraphs = blocks(body, source['id'])
            if not paragraphs:
                continue
            for paragraph in paragraphs:
                paragraph['id'] = f'p{count}'
                key = (source['id'], paragraph['id'])
                if key in edit_index:
                    edit = edit_index[key]
                    assert edit['section'] == f's{len(chapters)}', key
                    assert hashlib.sha256(paragraph['text'].encode()).hexdigest() == edit['before_sha256'], key
                    paragraph.update(text=edit['text'], layer=edit['layer'], reference=edit['reference'], collation=edit['status'])
                    applied.add(key)
                if source['id'] == 'zhengyi' and zhengyi:
                    record = zhengyi_index[paragraph['id']]
                    assert record['section'] == f's{len(chapters)}'
                    assert hashlib.sha256(paragraph['text'].encode()).hexdigest() == record['before_sha256']
                    parts = [{'text': p['text'], 'layer': p['layer']} for p in record['parts']]
                    paragraph.update(text=''.join(p['text'] for p in parts), parts=parts,
                                     layer=record['layer'], reference=record['reference'],
                                     reference_label=record['reference_label'])
                count += 1
            chapters.append({'id': f's{len(chapters)}', 'title': title, 'paragraphs': paragraphs})
        metadata = dict(source, sections=len(chapters), paragraphs=count,
                        characters=sum(len(p['text']) for s in chapters for p in s['paragraphs']))
        if any(e['book'] == source['id'] for e in edits):
            metadata['note'] += '；部分经文与署名解说已据识典逐字对齐补标点、标层次，属初校，非全书校定'
        if source['id'] == 'zhengyi' and zhengyi:
            assert count == len(zhengyi_index)
            metadata['note'] += '；已与东里排版文字逐卷核对，恢复经文、集解注、正义疏及序文边界，修正明确标点；同源核对不等于独立底本校勘'
        (OUT / f"{source['id']}.json").write_text(json.dumps(dict(metadata, chapters=chapters), ensure_ascii=False))
        catalog.append(metadata)
    assert applied == set(edit_index), 'Unapplied editorial corrections'
    (OUT / 'catalog.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2))
    print('\n'.join(f"{b['title']}: {b['sections']} sections, {b['characters']:,} characters" for b in catalog))

if __name__ == '__main__':
    build()
