"""Collate the full Liu-family Lunyu Zhengyi against Dongli's typeset text.
The stored source HTML is from the same edition as the imported text: agreement
checks transcription, not independent scholarly confirmation of the edition.
Preserve original paragraph IDs and characters; restore source paragraph/layer
boundaries inside those paragraphs. Reproducible build consumes the saved overlay.
"""
from pathlib import Path
from html.parser import HTMLParser
import argparse,bisect,collections,hashlib,html,json,re,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import sections,blocks
ROOT=Path(__file__).resolve().parents[2]

def sha(s):return hashlib.sha256(s.encode()).hexdigest()
def normalized(s):return ''.join(c for c in s if not c.isspace() and c!='/').translate(str.maketrans('（）','()'))

class Reader(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.chunks=[];self.on=False;self.stop=False;self.n=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='piclist':self.on=True
        if a.get('class')=='zhizheng':self.stop=True
        if tag not in ('br','hr','img','meta','input','link'):
            self.n+=1;self.stack.append((tag,a,self.n))
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0]==tag:self.stack=self.stack[:i];break
        if tag=='piclist':self.on=False
    def handle_data(self,text):
        if not self.on or self.stop:return
        text=re.sub(r'\s','',text)
        if not text:return
        kind='plain';node=0
        for tag,a,n in self.stack:
            if kind=='plain' and tag in ('p','h1','h2','h3'):node=n
            for k in ('zhengwen','jianshu','jiazhu'):
                if k in a.get('class','').split():kind=k;node=n
        if self.chunks and (kind,node)==(self.chunks[-1]['kind'],self.chunks[-1]['node']):
            self.chunks[-1]['text']+=text
        else:self.chunks.append(dict(text=text,kind=kind,node=node))

def layer(chunk,title):
    kind=chunk['kind'];text=chunk['text']
    # Two source paragraphs in Li Ren lack the ji an shu class. Their explicit
    # Zhengyi/annotation lemmata identify them as Liu's subcommentary.
    if kind=='jianshu' or (kind=='zhengwen' and text.startswith(('正義曰','○注：'))):return '疏 · 正义'
    if kind=='jiazhu':return '注 · 集解' if '〔注〕' in text else '夹注'
    if kind=='zhengwen':
        if title.startswith('卷二十四'):return '序文 · 何晏'
        if title.startswith('附録'):return '序文 · 郑玄逸文'
        return '经文'
    if title=='凡例':return '凡例' if len(text)>12 else '篇题／署名'
    if title=='劉恭冕後敍':return '后叙' if len(text)>12 else '篇题／署名'
    return '篇题／章数'

# Explicitly reviewed malformed title marks; the lexical characters are unchanged.
EXTRA_CLOSERS=(
 '《說文》通論》','《說文》注》','《漢書》成帝紀詔》','《禮記·禮器》注》',
 '《漢書》高紀注》','《白虎通》號篇》','《漢書》藝文志》','《白虎通》考黜篇》',
 '《漢書》韋玄成傳》','《白虎通》社稷篇》','《說文》𠧪[tiáo]部》',
 '《白虎通》諫諍篇》','《白虎通》禮樂篇》','《孔廟·禮器》碑》','《禮器》碑》',
 '《禮器》注》','《說文》繋傳》','《聘禮》記》','《說文》匚部》','《儀禮·聘禮》記》',
 '《禮器》疏》','《白虎通》紼冕篇》','《說文》手部》','《聘禮》注》',
 '《公羊》傳》','《聘禮》疏》','《儀禮·鄉飲酒》禮》','《大戴禮》·保傅篇》')
TITLE_FIXES={'《儀禮《聘禮》注》':'《儀禮·聘禮》注','《漢韓勅修孔廟《禮器》碑》':'《漢韓勅修孔廟禮器碑》'}
TITLE_FIXES.update({old:old[:-1] for old in EXTRA_CLOSERS})
TITLE_FIXES.update({'《隸釋載《漢樓壽碑》':'《隸釋》載《漢樓壽碑》',
 '《論釋稱公治長':'《論釋》稱公治長','《周官·司勳「':'《周官·司勳》「',
 '《爾雅·釋言：「':'《爾雅·釋言》：「','》廣雅》':'《廣雅》',
 '《學禮管釋引':'《學禮管釋》引','《學禮管釋：「':'《學禮管釋》：「'})

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source-dir',type=Path,default=ROOT.parent/'历代论语注解整理/原始网页');ap.add_argument('--index',type=Path,default=ROOT.parent/'历代论语注解整理/工作记录/正义_chapters.json');args=ap.parse_args()
    original=(ROOT/'sources/zhengyi.md').read_text();index=json.loads(args.index.read_text())
    edits=[];volumes=[];pid=0;examples=[];counts=collections.Counter();suspects=[]
    for si,((title,body),ref) in enumerate(zip(sections(original,'zhengyi'),index)):
        assert title==ref['title']
        raw=(args.source_dir/ref['file']).read_text();parser=Reader()
        # The source omits a closing note tag here, swallowing three canonical
        # passages. Repair markup only; the missing display bracket is logged below.
        broken='【〔注〕孔曰：「辨，別也。」\n子曰'
        repaired='【〔注〕孔曰：「辨，別也。」</span>\n子曰'
        if broken in raw:raw_for_parse=raw.replace(broken,repaired,1)
        else:raw_for_parse=raw
        parser.feed(raw_for_parse)
        chunks=parser.chunks;pars=blocks(body,'zhengyi');local=''.join(p['text'] for p in pars)
        reference=''.join(c['text'] for c in chunks)
        assert normalized(local)==normalized(reference),f'Non-layout textual difference: {title}; manual review required'
        # Compare punctuation too, except documented layout slashes and width of parentheses.
        ends=[];n=0
        for c in chunks:n+=len(normalized(c['text']));ends.append(n)
        cursor=0;local_offset=0;volume_parts=0
        for p in pars:
            before=p['text'];parts=[];start=0;active=None;comma_count=0
            for pos,c in enumerate(before):
                if c.isspace() or c=='/':idx=active if active is not None else bisect.bisect_right(ends,cursor)
                else:idx=bisect.bisect_right(ends,cursor);cursor+=1
                if active is not None and idx!=active:
                    parts.append({'start':start,'end':pos,'layer':layer(chunks[active],title),'source_node':chunks[active]['node']});start=pos
                active=idx
            if active is not None:parts.append({'start':start,'end':len(before),'layer':layer(chunks[active],title),'source_node':chunks[active]['node']})
            rendered=[];changes=[]
            for part in parts:
                text=before[part['start']:part['end']];after=text.replace(',','，')
                if after!=text:changes.append({'kind':'中文逗号统一','count':text.count(',')});counts['comma_fixes']+=text.count(',')
                if part['layer']=='注 · 集解' and text=='【〔注〕孔曰：「辨，別也。」':
                    after+='】';changes.append({'kind':'补齐注文外括号','before':text,'after':after});counts['note_bracket_fixes']+=1
                for old,new in TITLE_FIXES.items():
                    if old in after:
                        occurrences=after.count(old);after=after.replace(old,new)
                        changes.append({'kind':'书名号配对修正','before':old,'after':new,'count':occurrences})
                        counts['title_bracket_fixes']+=occurrences
                rendered.append(dict(part,text=after))
                # A diagnostic only: quoted speech can continue across paragraph boundaries.
                if after.count('《')!=after.count('》'):suspects.append({'section':f's{si}','paragraph':f'p{pid}','layer':part['layer'],'issue':'书名号数量不平衡，须结合上下文核对','text':after,'reference':ref['url']})
            after=''.join(x['text'] for x in rendered)
            new_layer=rendered[0]['layer'] if len(set(x['layer'] for x in rendered))==1 else '经注疏分层'
            e={'paragraph':f'p{pid}','section':f's{si}','before_sha256':sha(before),'before_layer':p['layer'],'layer':new_layer,'reference':ref['url'],'reference_label':'东里参照 · 校对','parts':rendered,'changes':changes}
            edits.append(e);pid+=1;volume_parts+=len(parts)
            if len(parts)>1:counts['split_paragraphs']+=1
            if p['layer']!=new_layer:counts['relabeled_paragraphs']+=1
            counts['display_parts']+=len(parts);counts['text_changed_paragraphs']+=bool(changes)
            if len(set(x['layer'] for x in rendered))>1 and len(examples)<8:examples.append({'section':e['section'],'paragraph':e['paragraph'],'before_layer':p['layer'],'layers':[x['layer'] for x in rendered],'reference':ref['url']})
        assert cursor==len(normalized(reference))
        volumes.append({'section':f's{si}','title':title,'url':ref['url'],'html_sha256':sha(raw),'source_kind':'本地已保存的东里完整HTML；本轮网上重新定位并抽核','comparison':'全卷逐字及标点相同（仅忽略空白、排版斜线及圆括号全半角）','paragraphs':len(pars),'display_parts':volume_parts})
    result={'book':'zhengyi','reference_book':'https://www.donglishuzhai.net/books/lunyuzhengyi.html','scope':'同源排版文字全卷核对；非独立底本全文校勘','source_sha256':sha(original),'volumes':volumes,'counts':dict(counts),'paragraphs':edits}
    (ROOT/'sources/zhengyi-collation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    report={'scope':result['scope'],'reference':result['reference_book'],'counts':dict(counts),'volumes':volumes,'examples':examples,'remaining_checks':suspects}
    (ROOT/'collation/zhengyi-typeset-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    table=''.join(f'<tr><td>{html.escape(v["title"])}</td><td>{v["paragraphs"]}</td><td>{v["display_parts"]}</td><td><a href="{v["url"]}">排版文字参照</a></td></tr>' for v in volumes)
    corrections=''.join(f'<li><a href="{e["reference"]}">{e["section"]} / {e["paragraph"]}</a>：'+html.escape('；'.join(c['kind']+('：'+c['before']+' → '+c['after'] if 'before' in c else ' '+str(c.get('count',''))) for c in e['changes']))+'</li>' for e in edits if e['changes'])
    page=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>论语正义 · 排版文字校对</title><style>body{{max-width:1050px;margin:50px auto;padding:0 24px;background:#f4f0e7;color:#28392f;font:16px/1.9 system-ui}}h1,h2{{font-family:serif}}table{{width:100%;border-collapse:collapse}}td,th{{padding:8px;border-bottom:1px solid #ccc;text-align:left}}a{{color:#326953}}.note{{padding:18px;background:#fff9}}</style><h1>论语正义 · 排版文字校对</h1><p>2026-10-22 · 刘宝楠、刘恭冕本</p><p class="note">参照<a href="https://www.donglishuzhai.net/books/lunyuzhengyi.html">东里书斋排版文字</a>。二十四卷及凡例、郑玄序逸文、刘恭冕后叙共27节、3,072个原有段落已全量核对；忽略排版空白、斜线和圆括号全半角后，导入正文与已保存的完整网页正文相同。两者同源，这证明录入一致，不能证明底本本身没有讹误。网络直连本轮超时，使用已有完整HTML并通过网上章页抽核；不是新抓取的全站快照。</p><p>恢复 {counts['split_paragraphs']:,} 个合并段落内部的排版边界，共 {counts['display_parts']:,} 个显示分段。经文、集解注、正义疏、篇题章数、序文与后叙分别标明。修正 {counts['comma_fixes']} 处中文逗号、{counts['title_bracket_fixes']} 处书名号、{counts['note_bracket_fixes']} 处注文括号，涉及 {counts['text_changed_paragraphs']} 个原有段落。原字与原始下载保留，段号及书签定位不变。</p><p>网页结构例外：颜渊“辨，别也”处遗漏注释闭合标签，经文被包入注文；里仁两段正义疏缺少疏文样式。均按明确文意和上下文修正。原有长段截断仍可能发生在同一层次内，不代表原书章句划分。</p><p><a href="zhengyi-typeset-audit.json">完整核对记录</a> · <a href="../sources/zhengyi-collation.json">逐段修改及原文哈希</a></p><h2>全书覆盖</h2><table><tr><th>卷目</th><th>原段数</th><th>分层后显示段数</th><th>参照</th></tr>{table}</table><h2>标点修正记录</h2><ul>{corrections}</ul></html>'''
    (ROOT/'collation/zhengyi-typeset-report.html').write_text(page)
    print(json.dumps(counts,ensure_ascii=False));print('paragraphs',pid,'volumes',len(volumes),'bracket candidates',len(suspects))
if __name__=='__main__':main()
