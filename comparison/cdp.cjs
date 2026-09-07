const fs=require('fs');
const puppeteer=require('/opt/client/node_modules/puppeteer-core');
const [name,endpoint,url]=process.argv.slice(2);
const output=process.env.BENCH_RESULTS || '/bench/results';
const probe=fs.readFileSync('/bench/probe.js','utf8');
const result={name,adapter:'puppeteer-core',runs:[],errors:[]};
(async()=>{
 let browser;
 try{
  browser=await puppeteer.connect({browserWSEndpoint:endpoint,protocolTimeout:12000,defaultViewport:null});
  for(let i=0;i<3;i++){
   const page=await browser.newPage();page.setDefaultTimeout(10000);
   try{await page.setViewport({width:800,height:600})}catch(e){result.viewport_error=e.message}
   const t=performance.now();
   try{
    await page.goto(url,{waitUntil:'load',timeout:15000});
    await page.waitForFunction(()=>window.fixtureReady===true,{timeout:10000});
    const ms=performance.now()-t;
    const checks=await page.evaluate(`(${probe})()`);
    result.runs.push({navigation_ms:ms,checks});
    if(i===0){
     try{await page.type('#name','Lupa');await page.click('#go');result.interaction=await page.$eval('#greeting',el=>el.textContent)}catch(e){result.interaction_error=e.message}
     await page.evaluate(()=>{document.querySelector('#name').value='';document.querySelector('#greeting').textContent=''});
     for(const [key,action] of Object.entries({screenshot:()=>page.screenshot({path:`${output}/${name}.png`}),pdf:()=>page.pdf({path:`${output}/${name}.pdf`,format:'A4',printBackground:true})})){
      const start=performance.now();try{await action();result[key]={ok:true,ms:performance.now()-start}}catch(e){result[key]={ok:false,error:e.message}}
     }
    }
   }catch(e){result.errors.push(e.message)}finally{await page.close().catch(()=>{})}
  }
 }catch(e){result.errors.push(e.stack)}finally{if(browser)await browser.disconnect();fs.writeFileSync(`${output}/${name}.json`,JSON.stringify(result,null,2));console.log(JSON.stringify(result));}
})();
