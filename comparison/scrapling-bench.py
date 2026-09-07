import os
import json,sys,time,traceback
from pathlib import Path
from importlib.metadata import version
from scrapling.fetchers import DynamicSession, Fetcher

url=sys.argv[1]
output=Path(os.environ.get('BENCH_RESULTS','/bench/results'))
result={'name':'scrapling','version':version('scrapling'),'adapter':'DynamicSession + system Chromium','runs':[]}
probe=Path('/bench/probe.js').read_text()
try:
    start=time.perf_counter()
    with DynamicSession(headless=True,executable_path='/usr/bin/chromium',extra_flags=['--no-sandbox'],google_search=False,timeout=15000,additional_args={'viewport':{'width':800,'height':600}}) as session:
        result['startup_ms']=(time.perf_counter()-start)*1000
        for i in range(3):
            row={}
            def action(page):
                page.wait_for_function('window.fixtureReady === true',timeout=10000)
                row['checks']=page.evaluate(probe)
                row['navigation_to_ready_ms']=(time.perf_counter()-start)*1000
                if i==0:
                    page.fill('#name','Lupa');page.click('#go')
                    result['interaction']=page.locator('#greeting').inner_text()
                    page.evaluate("() => {document.querySelector('#name').value='';document.querySelector('#greeting').textContent=''}")
                    for name,fn in [('screenshot',lambda:page.screenshot(path=str(output/'scrapling.png'))),('pdf',lambda:page.pdf(path=str(output/'scrapling.pdf'),format='A4',print_background=True))]:
                        t=time.perf_counter()
                        try:fn();result[name]={'ok':True,'ms':(time.perf_counter()-t)*1000}
                        except Exception as e:result[name]={'ok':False,'error':str(e)}
            start=time.perf_counter()
            response=session.fetch(url,page_action=action)
            row['total_ms']=(time.perf_counter()-start)*1000
            row['extracted_cards']=response.css('.card::text').getall()
            result['runs'].append(row)
    start=time.perf_counter();response=Fetcher.get(url)
    result['http_only']={'ms':(time.perf_counter()-start)*1000,'cards':response.css('.card::text').getall(),'ready_text':response.css('#ready::text').get()}
except Exception:
    result['error']=traceback.format_exc()
finally:
    (output/'scrapling.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
