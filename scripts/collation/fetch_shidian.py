"""Read public Shidian chapter HTML; no authentication or private APIs.
Resume from .local/shidian/reference; record missing/encrypted paragraphs explicitly.
"""
from pathlib import Path
import concurrent.futures, hashlib, json, re, threading, time, urllib.request, urllib.error
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'.local/shidian'
OUT=BASE/'reference'
SEEDS={'yishu':'yishu_data.json','sishu':'sishu_data.json','jingyi':'SK0542_sample_data.json','yulei':'yulei_chapter_data.json'}
SEED_URLS={
    'yishu':'https://www.shidianguji.com/book/NA01081/chapter/1m3lh4r9khv76',
    'sishu':'https://www.shidianguji.com/book/SK0540/chapter/1jurjtkgmfokz',
    'jingyi':'https://www.shidianguji.com/book/SK0542/chapter/1kezibi8fp0z7',
    'yulei':'https://www.shidianguji.com/book/SK1308/chapter/1kg1suqdly6u3',
}
LOCK=threading.Lock(); next_request=0

def flatten(chapters, ancestors=()):
    for c in chapters:
        yield dict(c,ancestors=list(ancestors))
        yield from flatten(c.get('subChapters',[]), ancestors+(c['chapterId'],))

def extract(html):
    m=re.search(r'window\._ROUTER_DATA = (.*?)</script>',html,re.S)
    if not m: return None
    data=json.loads(m[1].strip().rstrip(';'))
    return next((v for v in data['loaderData'].values() if isinstance(v,dict) and 'paragraphList' in v),None)

def fetch_book(item):
    global next_request
    key,seed=item
    if not (BASE/seed).exists():
        with urllib.request.urlopen(SEED_URLS[key],timeout=25) as response:
            data=extract(response.read().decode('utf-8'))
        if not data or 'bookInfo' not in data:raise RuntimeError('Public seed page has no readable catalog: '+key)
        (BASE/seed).write_text(json.dumps({k:data[k] for k in ('bookInfo','paragraphList','ssrChapterId')},ensure_ascii=False))
    data=json.loads((BASE/seed).read_text()); info=data['bookInfo']; book=info['bookId']; dest=OUT/key; dest.mkdir(parents=True,exist_ok=True)
    chapters=list(flatten(info['catalog']['chapters'])); paras={}; failures=[]; pages=[]
    def absorb(d,url,sha):
        for p in d.get('paragraphList',[]):
            if p.get('contentEncryptType',0)!=0:
                failures.append({'url':url,'reason':'encrypted content','paragraph':p['paragraphId']});continue
            paras[p['paragraphId']]=dict(p,reference_url=url,response_sha256=sha)
    seed_url=f'https://www.shidianguji.com/book/{book}/chapter/{data["ssrChapterId"]}'
    absorb(data,seed_url,hashlib.sha256((BASE/seed).read_bytes()).hexdigest())
    def save():
        counts={}
        for p in paras.values(): counts[p['chapterId']]=counts.get(p['chapterId'],0)+1
        coverage=[{'chapter':c['chapterId'],'title':''.join(x.get('content','') for x in c['chapterName']),'expected':c.get('paragraphCount',0),'received':counts.get(c['chapterId'],0)} for c in chapters]
        summary={'book':book,'local_book':key,'version':info.get('version'),'edition':info.get('edition'),'chapters':chapters,'coverage':coverage,'failures':failures,'paragraphs':sorted(paras.values(),key=lambda p:(p.get('chapterOrder',0),p.get('inChapterOrder',0)))}
        (dest/'corpus.json').write_text(json.dumps(summary,ensure_ascii=False))
    for idx,c in enumerate(chapters):
        cid=c['chapterId'];expected=c.get('paragraphCount',0)
        if sum(p['chapterId']==cid for p in paras.values())>=expected:continue
        url=f'https://www.shidianguji.com/book/{book}/chapter/{cid}'; cache=dest/(cid+'.json')
        if cache.exists():
            record=json.loads(cache.read_text()); absorb(record['data'],url,record['sha256']); continue
        with LOCK:
            delay=max(0,next_request-time.monotonic());next_request=max(time.monotonic(),next_request)+.6
        if delay:time.sleep(delay)
        try:
            with urllib.request.urlopen(url,timeout=25) as response: raw=response.read()
            d=extract(raw.decode('utf-8'))
            if d is None:
                failures.append({'url':url,'reason':'HTML contains no readable chapter data'});continue
            # Keep only public book and paragraph data; omit unrelated page configuration.
            d={k:d[k] for k in ['paragraphList','ssrChapterId']}
            record={'url':url,'sha256':hashlib.sha256(raw).hexdigest(),'fetched_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'data':d}
            cache.write_text(json.dumps(record,ensure_ascii=False));absorb(d,url,record['sha256']); pages.append(url)
        except urllib.error.HTTPError as e:
            failures.append({'url':url,'reason':f'HTTP {e.code}'})
            if e.code in (401,403,429):break
        except Exception as e:failures.append({'url':url,'reason':str(e)})
        if len(pages)%20==0: print(key,'pages',len(pages),'paragraphs',len(paras),'chapter',idx+1,'/',len(chapters),flush=True)
        if len(pages)%10==0:save()
    save()
    print(key,'DONE',len(paras),'/',sum(c.get('paragraphCount',0) for c in chapters),'failures',len(failures),flush=True)
    return key

if __name__ == "__main__":
    OUT.mkdir(parents=True,exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(fetch_book,SEEDS.items()))
