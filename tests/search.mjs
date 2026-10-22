import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs';
import path from 'node:path';
const root=path.resolve(import.meta.dirname,'../docs');
let result;
const context=vm.createContext({fetch:async url=>({ok:true,json:async()=>JSON.parse(fs.readFileSync(path.join(root,'assets',url),'utf8'))}),postMessage:d=>{result=d;}});
context.self=context;
context.importScripts=name=>vm.runInContext(fs.readFileSync(path.join(root,'assets',name),'utf8'),context);
vm.runInContext(fs.readFileSync(path.join(root,'assets/search-worker.js'),'utf8'),context);
const books=['yishu','sishu','yulei','jingyi','jijie'];
async function search(query,book='',offset=0){await context.onmessage({data:{id:1,query,book,offset,books}});return result;}
test('simplified and traditional queries return identical full-corpus matches',async()=>{const a=await search('学而时习之'),b=await search('學而時習之');assert.ok(a.total>20);assert.equal(a.total,b.total);assert.equal(a.results.length,20);});
test('punctuation, scope and pagination preserve source references',async()=>{const a=await search('学而，时习之','jijie');assert.ok(a.total>0);assert.ok(a.results.every(r=>r.book==='jijie'));const b=await search('学而时习之','',20);assert.ok(b.results.length>0);for(const r of b.results){const book=JSON.parse(fs.readFileSync(path.join(root,'data',r.book+'.json')));assert.equal(book.chapters.find(s=>s.id===r.section).paragraphs.find(p=>p.id===r.id).text,r.text);}});
test('empty and missing queries produce no matches',async()=>{assert.equal((await search('   ，')).total,0);assert.equal((await search('不存在的检索字句XYZ')).total,0);});
