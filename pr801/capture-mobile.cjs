const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root=__dirname, rows=[];
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const server=http.createServer((req,res)=>{
 const url=new URL(req.url,'http://localhost'),rel=decodeURIComponent(url.pathname).replace(/^\//,'');
 const file=path.resolve(root,rel.endsWith('/')?rel+'index.html':rel);
 if(!file.startsWith(root+path.sep)||!fs.existsSync(file)||!fs.statSync(file).isFile()){res.writeHead(404);res.end();return;}
 const types={'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json'};
 res.setHeader('Content-Type',types[path.extname(file)]||'application/octet-stream');res.end(fs.readFileSync(file));
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const port=server.address().port;
 let browser;
 try{
  browser=await chromium.launch({channel:'chrome',headless:true});
  for(const width of [390])for(const scenario of ['good','small','missing'])for(const side of ['before','after']){
   const context=await browser.newContext({viewport:{width,height:1400},colorScheme:'light'}),page=await context.newPage(),errors=[],responses=[];
   page.on('pageerror',e=>errors.push(String(e)));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
   page.on('response',r=>responses.push(r));
   const url=`http://127.0.0.1:${port}/${side}/?data=${scenario}.json`;
   await page.goto(url,{waitUntil:'networkidle'});await page.waitForSelector('#content:not([hidden])');
   const tiles=await page.locator('#oneshot .tile').evaluateAll(els=>els.map(e=>({label:e.querySelector('.label').textContent,value:e.querySelector('.value').textContent,detail:e.querySelector('.detail').textContent})));
   const dimensions=await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,viewport:window.innerWidth}));
   assert.deepEqual(errors,[]);assert.ok(dimensions.scroll<=dimensions.viewport,JSON.stringify(dimensions));
   assert.equal(tiles.length,side==='before'?0:4);
   if(side==='after'){
    if(scenario==='good'){
     assert.equal(tiles[0].value,'2 of 5 · 40%');assert.equal(tiles[1].value,'1 / 5');
     assert.match(tiles[2].value,/60 min/);assert.equal(tiles[3].value,'6 of 7');
     assert.ok(tiles.every(x=>x.detail.includes('unknown: 1')));
    }else{
     assert.ok(tiles.every(x=>x.value==='Not enough data'));
     assert.ok(tiles.every(x=>x.detail.includes('unknown:')));
     assert.match(tiles[3].detail,scenario==='missing'?/unknown: 8/:/unknown: 0/);
    }
   }
   const received=[];
   for(const r of responses){
    assert.equal(r.status(),200,r.url());const relative=new URL(r.url()).pathname.replace(/^\//,'');
    const filename=relative.endsWith('/')?relative+'index.html':relative;
    const bytes=await r.body();assert.equal(sha(bytes),sha(fs.readFileSync(path.join(root,filename))));
    received.push({file:filename,sha256:sha(bytes),status:r.status()});
   }
   const screenshot=`${side}-${scenario}-${width}x1400.png`,captured_at=new Date().toISOString();
   await page.screenshot({path:path.join(root,screenshot),fullPage:false});
   rows.push({side,scenario,width,captured_at,url,tiles,dimensions,errors,received,screenshot,sha256:sha(fs.readFileSync(path.join(root,screenshot)))});
   console.log(`${side} ${scenario} ${width}: PASS`);await context.close();
  }
 }finally{if(browser)await browser.close();server.close();fs.writeFileSync(path.join(root,'capture-results-mobile.json'),JSON.stringify({layer:'synthetic-fixture supporting static UI proof, not real integration',driver_sha256:sha(fs.readFileSync(__filename)),captures:rows},null,2)+'\n');}
})().catch(e=>{console.error(e);process.exitCode=1;});
