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
  for(const width of [1440,375])for(const scenario of ['real'])for(const side of ['before','after']){
   const context=await browser.newContext({viewport:{width,height:width===375?812:900},colorScheme:'light'}),page=await context.newPage(),errors=[],responses=[];
   page.on('pageerror',e=>errors.push(String(e)));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
   page.on('response',r=>responses.push(r));
   const url=`http://127.0.0.1:${port}/${side}/?data=${scenario}.json`;
   await page.goto(url,{waitUntil:'networkidle'});await page.waitForSelector('#content:not([hidden])');
   const tiles=await page.locator('#oneshot .tile').evaluateAll(els=>els.map(e=>({label:e.querySelector('.label').textContent,value:e.querySelector('.value').textContent,detail:e.querySelector('.detail').textContent})));
   const dimensions=await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,viewport:window.innerWidth}));
   assert.deepEqual(errors,[]);assert.ok(dimensions.scroll<=dimensions.viewport,JSON.stringify(dimensions));
   assert.equal(tiles.length,side==='before'?0:4);
   if(side==='after'){
    const payload=JSON.parse(fs.readFileSync(path.join(root,side,'real.json')));
    const stats=require(path.join(root,'after','stats.js'));
    const expected=stats.oneShot(payload.prs);
    assert.ok(tiles.every(x=>x.detail.includes('unknown:')));
    assert.equal(tiles[3].value,`${expected.counts.reached} of ${expected.counts.started}`);
   }
   const received=[];
   for(const r of responses){
    assert.equal(r.status(),200,r.url());const relative=new URL(r.url()).pathname.replace(/^\//,'');
    const filename=relative.endsWith('/')?relative+'index.html':relative;
    const bytes=await r.body();assert.equal(sha(bytes),sha(fs.readFileSync(path.join(root,filename))));
    received.push({file:filename,sha256:sha(bytes),status:r.status()});
   }
   if(side==='after') await page.locator('#oneshot').screenshot({path:path.join(root,`after-real-${width}-tiles.png`)});
   const screenshot=`${side}-${scenario}-${width}.png`,captured_at=new Date().toISOString();
   await page.screenshot({path:path.join(root,screenshot),clip:{x:0,y:0,width,height:width===375?1400:900}});
   rows.push({side,scenario,width,captured_at,url,tiles,dimensions,errors,received,screenshot,sha256:sha(fs.readFileSync(path.join(root,screenshot)))});
   console.log(`${side} ${scenario} ${width}: PASS`);await context.close();
  }
 }finally{if(browser)await browser.close();server.close();fs.writeFileSync(path.join(root,'capture-results-real.json'),JSON.stringify({layer:'real cached public-repository records served by real local static HTTP app; not fresh collector execution',driver_sha256:sha(fs.readFileSync(__filename)),captures:rows},null,2)+'\n');}
})().catch(e=>{console.error(e);process.exitCode=1;});
