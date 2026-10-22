importScripts('search-fold.js');
const fold = s => Array.from(s.normalize('NFKC').toLowerCase(), c => self.CarrotFoldMap[c] || c).join('').replace(/[\s\p{P}]/gu, '');
let corpus;
onmessage = async ({data}) => {
  try {
    corpus ||= Promise.all(data.books.map(async b => {
      const r = await fetch(`../data/${b}.json`); if (!r.ok) throw Error('资料加载失败');
      const book = await r.json();
      return book.chapters.flatMap(s => s.paragraphs.map(p => ({book:book.id,title:book.title,section:s.id,heading:s.title,id:p.id,text:p.text,normalized:fold(p.text)})));
    })).then(all => all.flat());
    const rows = await corpus;
    const query = fold(data.query);
    const matches = query ? rows.filter(p => (!data.book || p.book === data.book) && p.normalized.includes(query)) : [];
    postMessage({id:data.id,total:matches.length,results:matches.slice(data.offset,data.offset+20).map(({normalized,...p}) => p)});
  } catch(error) { corpus = null; postMessage({id:data.id,error:error.message}); }
};
