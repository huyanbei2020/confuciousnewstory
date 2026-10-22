"""Audit every published paragraph against retrieved, versioned Shidian text.
Exact matching folds character variants for alignment ONLY. It is not scholarly approval.
"""
from pathlib import Path
from collections import Counter
from array import array
import bisect, csv, hashlib, html, json, re, unicodedata, sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build import sections, blocks
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'collation'; OUT.mkdir(exist_ok=True)
fold_script=(ROOT/'docs/assets/search-fold.js').read_text()
FOLD=json.loads(fold_script[fold_script.index('{'):fold_script.rindex('}')+1])

def normalize(text, offsets=False):
    chars=[]; positions=array('I')
    for i,c in enumerate(text):
        for c2 in unicodedata.normalize('NFKC',c):
            if c2.isspace() or unicodedata.category(c2).startswith('P'):continue
            c2=FOLD.get(c2,c2)
            chars.append(c2)
            if offsets:positions.extend([i]*len(c2))
    result=''.join(chars)
    return (result,positions) if offsets else result

def main():
    results=[]; details={}; candidates=[]
    for b in json.loads((ROOT/'sources/manifest.json').read_text()):
        chapters=[];count=0
        for heading,body in sections((ROOT/'sources'/b['file']).read_text(encoding='utf-8-sig'),b['id']):
            paragraphs=blocks(body,b['id'])
            if not paragraphs:continue
            for p in paragraphs:
                p['id']=f'p{count}';count+=1
            chapters.append({'id':f's{len(chapters)}','title':heading,'paragraphs':paragraphs})
        book={'chapters':chapters}
        b['characters']=sum(len(p['text']) for s in chapters for p in s['paragraphs'])
        ref_path=ROOT/f'.local/shidian/reference/{b["id"]}/corpus.json'
        ref=json.loads(ref_path.read_text()) if ref_path.exists() else None
        ref_text='';segments=[];ends=[]
        if ref:
            texts=[];pos=0
            for p in ref['paragraphs']:
                for line in json.loads(p['content']).get('lines',[]):
                    text=line.get('content','')
                    if not text:continue
                    texts.append(text);pos+=len(text);ends.append(pos)
                    segments.append({'url':p['reference_url'],'paragraph':p['paragraphId'],'chapter':p['chapterId'],'line':line['lineId'],'type':line['lineType'],'response_sha256':p['response_sha256']})
            ref_text=''.join(texts)
        ref_norm,positions=normalize(ref_text,True);rows=[]
        for s in book['chapters']:
            for p in s['paragraphs']:
                text=p['text'];norm=normalize(text); issues=[]
                if not p['layer']:issues.append('未分层')
                if len(text)>100 and not re.search('[，。；？！]',text):issues.append('长段缺少句读')
                if any(unicodedata.category(c)=='Co' for c in text):issues.append('私用区缺字编码')
                if re.search('[□�]',text):issues.append('缺字或替代符')
                if re.search('[a-zA-Z]{4,}',text):issues.append('拉丁字符/残留标记待核')
                if b['id']=='yulei' and '经文' in p['layer']:issues.append('语录引经不宜直接标作独立经文')
                row={'section':s['id'],'heading':s['title'],'paragraph':p['id'],'layer':p['layer'],'characters':len(text),'issues':issues,'text':text}
                start=ref_norm.find(norm) if len(norm)>=12 else -1
                if ref is None:row['comparison']='未取得识典参照'
                elif len(norm)<12:row['comparison']='短句需结合上下文定位'
                elif start<0:row['comparison']='未逐字对齐（异文/漏字/重排/参照缺页待核）'
                elif ref_norm.find(norm,start+1)>=0:row['comparison']='同文多处出现，定位待核'
                else:
                    a=positions[start];z=positions[start+len(norm)-1]+1
                    # Include trailing punctuation, not a subsequent word.
                    line_end=ends[bisect.bisect_left(ends,z)]
                    while z<line_end and (ref_text[z].isspace() or unicodedata.category(ref_text[z]).startswith('P')):z+=1
                    matched=ref_text[a:z];row['comparison']='字形归一后逐字对齐'
                    row['reference_text']=matched
                    first=bisect.bisect_right(ends,a);last=bisect.bisect_left(ends,z)
                    row['reference_segments']=segments[first:last+1]
                    row['punctuation_equal']=re.sub(r'\s','',normalize_punctuation(text))==re.sub(r'\s','',normalize_punctuation(matched))
                    if not row['punctuation_equal']:issues.append('标点/断句与参照不同，待核')
                    # Candidates only: never silently promote a source website to a corrected edition.
                    if '长段缺少句读' in issues and re.search('[，。；？！]',matched):
                        candidates.append({'book':b['id'],'paragraph':p['id'],'heading':s['title'],'before':text,'reference':matched,'url':segments[first]['url'],'status':'待核，不自动改字'})
                if ref and row['comparison'].startswith('未逐字对齐') and len(norm)>=24:
                    hints=[]
                    for offset in dict.fromkeys((0,len(norm)//2,len(norm)-16)):
                        fragment=norm[offset:offset+16];hit=ref_norm.find(fragment)
                        if hit>=0 and ref_norm.find(fragment,hit+1)<0:
                            seg=segments[bisect.bisect_right(ends,positions[hit])]
                            hints.append(dict(seg,matched_fragment=fragment,status='仅片段定位，不能作为全文相同或改文依据'))
                    if hints:row['candidate_reference_segments']=hints
                rows.append(row)
        counts=Counter(r['comparison'] for r in rows);issue_counts=Counter(i for r in rows for i in r['issues'])
        summary={'id':b['id'],'title':b['title'],'characters':b['characters'],'paragraphs':len(rows),'comparison':dict(counts),'issues':dict(issue_counts),'reference':None if not ref else {'book':ref['book'],'version':ref['version'],'edition':ref['edition'],'expected_paragraphs':sum(c['expected'] for c in ref['coverage']),'received_paragraphs':len(ref['paragraphs']),'complete_chapters':sum(c['received']>=c['expected'] for c in ref['coverage']),'chapters':len(ref['chapters']),'failures':ref['failures']},'source_sha256':b['sha256']}
        results.append(summary);details[b['id']]=rows
        (OUT/(b['id']+'-audit.json')).write_text(json.dumps({'summary':summary,'rows':rows},ensure_ascii=False,indent=2))
        print(b['title'],dict(counts),dict(issue_counts),flush=True)
    (OUT/'summary.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    (OUT/'punctuation-candidates.json').write_text(json.dumps(candidates,ensure_ascii=False,indent=2))
    with (OUT/'issues.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f);w.writerow(['书名','卷目','段号','现有层次','比对状态','待核问题','本地文本','识典对应文本','参照链接'])
        for b in results:
            for r in details[b['id']]:
                if r['issues'] or r['comparison']!='字形归一后逐字对齐':
                    references=r.get('reference_segments') or r.get('candidate_reference_segments') or []
                    links='；'.join(dict.fromkeys(s['url'] for s in references))
                    if r.get('candidate_reference_segments'):links='仅片段定位：'+links
                    w.writerow([b['title'],r['heading'],r['paragraph'],r['layer'],r['comparison'],'；'.join(r['issues']),r['text'],r.get('reference_text',''),links])
    render(results,details)

def normalize_punctuation(text):
    # Fold glyphs while retaining punctuation for the punctuation comparison.
    return ''.join(FOLD.get(c,c) for c in unicodedata.normalize('NFKC',text))

def render(books,details):
    esc=html.escape
    cards=''
    for b in books:
        ref=b['reference']; coverage='未定位到刘氏《论语正义》独立书页' if not ref else f"{ref['received_paragraphs']:,} / {ref['expected_paragraphs']:,} 个参照段；{ref['complete_chapters']} / {ref['chapters']} 个目录节点完整"
        edition='' if not ref else f"<p>识典：{esc(ref['edition']['edition'])} · 数据版本 {ref['version']}</p>"
        cards+=f'<section><h2>{esc(b["title"])}</h2>{edition}<p>{b["paragraphs"]:,} 个本地段 · {b["characters"]:,} 字</p><p>{esc(coverage)}</p><ul>'+''.join(f'<li>{esc(k)}：{v:,}</li>' for k,v in b['comparison'].items())+'</ul><ul>'+''.join(f'<li>{esc(k)}：{v:,}</li>' for k,v in b['issues'].items())+f'</ul><a href="{b["id"]}-audit.json">逐段记录 JSON</a></section>'
    document='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>五部原典 · 识典参照校对记录</title><style>body{max-width:1100px;margin:60px auto;padding:0 24px;background:#f4f0e7;color:#28392f;font:16px/1.9 system-ui}h1,h2{font-family:serif;font-weight:400}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:24px}section{border:1px solid #ccc5b7;padding:24px;background:#fff9}a{color:#326953}.notice{border-left:3px solid #946047;padding:12px 22px;background:#fff8}</style><h1>五部原典 · 识典参照校对记录</h1><p>2026-10-22 · 导入原稿的全库机器检查与逐段对齐记录（修订前基线）</p><div class="notice">此记录不是“全文已校定”的证明。字形归一后相同，仅说明可比对；不证明标点、层次或底本一致。未对齐的段落、参照缺页及现代标点差异均须复核。识典的小字格式仅保留为原始 lineType，不直接等同于经、传、注、疏。仅逐字对齐、明确署名的《论孟精义》解说及另行核对的两段经文另作保留原字的初校，修改逐条保存于 sources/editorial.json；其余候选不覆盖线上正文。</div><p><a href="issues.csv">下载全量待核清单 CSV</a> · <a href="punctuation-candidates.json">下载标点候选 JSON</a> · <a href="summary.json">覆盖统计 JSON</a></p><main>'''+cards+'</main></html>'
    (OUT/'report.html').write_text(document)

if __name__=='__main__':main()
