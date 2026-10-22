"""Prepare conservative first-pass corrections, keeping every original lexical character.
Only commentary paragraphs with an unambiguous named commentator and an exact
variant-folded match qualify. These are reference-based initial edits, not final collation.
"""
from pathlib import Path
import hashlib,json,re,unicodedata
from audit import normalize
ROOT=Path(__file__).resolve().parents[2]
COMMENTATOR=re.compile(r'^(?:伊川(?:解|語錄|语录)?|明道(?:解|語錄|语录)?|横渠|橫渠|范|呂|吕|謝|谢|游|楊|杨|侯|尹)(?:先生)?曰')
# These two complete passages were separately checked against the reference text.
REVIEWED_CANON={'p15':'子曰学而时习之不亦说乎有朋自逺方来不亦乐乎人不知而不愠不亦君子乎','p22':'有子曰其为人也孝弟而好犯上者鲜矣不好犯上而好作乱者未之有也君子务本本立而道生孝弟也者其为仁之本与'}
def lexical(s):return ''.join(c for c in s if not c.isspace() and not unicodedata.category(c).startswith('P'))
def punctuate(original,reference):
    chars=lexical(original);other=lexical(reference)
    if len(chars)!=len(other) or any(normalize(a)!=normalize(b) for a,b in zip(chars,other)):
        return None
    i=0;out=[]
    for c in reference:
        if c.isspace():continue
        if unicodedata.category(c).startswith('P'):out.append(c)
        else:out.append(chars[i]);i+=1
    result=''.join(out)
    assert lexical(result)==lexical(original)
    return result

def main():
    data=json.loads((ROOT/'collation/jingyi-audit.json').read_text());edits=[]
    for row in data['rows']:
        canonical=row['paragraph'] in REVIEWED_CANON and normalize(row['text'])==normalize(REVIEWED_CANON[row['paragraph']])
        if row['comparison']!='字形归一后逐字对齐' or not (canonical or COMMENTATOR.match(row['text'])):continue
        segments=row.get('reference_segments',[])
        if not segments or len({s['chapter'] for s in segments})!=1:continue
        original=row['text'];replacement=original;reason=['已核对本段为完整的《论语·学而》经文章句。' if canonical else '本段以明确的宋儒署名起首，按诸家解说标示；内部引经仍属解说。']
        # Never replace existing punctuation or a fragment beginning mid-commentary.
        if not any(unicodedata.category(c).startswith('P') for c in original):
            candidate=punctuate(original,row['reference_text'])
            if candidate and candidate!=original:
                replacement=candidate;reason.append('与识典逐字归一对齐，移入来源标点；保留本地全部原字。')
        edits.append({'book':'jingyi','section':row['section'],'paragraph':row['paragraph'],'before':original,'before_sha256':hashlib.sha256(original.encode()).hexdigest(),'text':replacement,'layer':'经文' if canonical else '诸家解说','reason':reason,'reference':segments[0]['url'],'reference_paragraphs':list(dict.fromkeys(s['paragraph'] for s in segments)),'reference_text':row['reference_text'],'status':'识典参照初校，非逐句人工校定'})
    (ROOT/'sources/editorial.json').write_text(json.dumps({'policy':'仅限逐字对齐的明确署名解说及另行核对的两段经文；保留原字；未对齐、原有标点及底本异文不自动覆盖。','edits':edits},ensure_ascii=False,indent=2)+'\n')
    punctuation_count=sum(e['before']!=e['text'] for e in edits)
    report=ROOT/'collation/report.html'
    if report.exists():
        content=re.sub(r'<p id="applied-edits">.*?</p>','',report.read_text())
        note=f'<p id="applied-edits">本轮已应用：《论孟精义》{len(edits):,} 段层次初校，其中 {punctuation_count:,} 段补标点；《朱子语类》285 段引文标签改为待核。<a href="../sources/editorial.json">查看逐条修改记录</a>。下列数字仍是修订前基线，不能视为剩余问题数。</p>'
        report.write_text(content.replace('<main>',note+'<main>',1))
    print('layer corrections',len(edits),'punctuation corrections',punctuation_count)
if __name__=='__main__':main()
