import os
import asyncio,base64,json,sys,time,traceback,subprocess,tempfile,os,signal
from pathlib import Path
from importlib.metadata import version
from browser_use import BrowserSession

output=Path(os.environ.get('BENCH_RESULTS','/bench/results'))
result={'name':'browser-use','version':version('browser-use'),'adapter':'BrowserSession Actor API + system Chromium; no LLM','runs':[]}
def decode(value):
    if value=='True':return True
    if value=='False':return False
    try:return json.loads(value)
    except (TypeError,ValueError):return value
async def main():
    profile=tempfile.TemporaryDirectory(prefix='bu-comparison-')
    process=subprocess.Popen(['/usr/bin/chromium','--headless','--no-sandbox','--disable-dev-shm-usage','--remote-debugging-port=0','--user-data-dir='+profile.name,'--window-size=800,600','about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    browser=None
    try:
        for _ in range(300):
            if process.poll() is not None:raise RuntimeError(f'Chromium exited: {process.returncode}')
            try:
                port,path=(Path(profile.name)/'DevToolsActivePort').read_text().splitlines()[:2]
                break
            except Exception:await asyncio.sleep(.1)
        else:raise TimeoutError('Chromium did not publish DevToolsActivePort')
        browser=BrowserSession(cdp_url=f'ws://127.0.0.1:{port}{path}',enable_default_extensions=False,viewport={'width':800,'height':600})
        t=time.perf_counter();await browser.start();result['startup_ms']=(time.perf_counter()-t)*1000
        result['startup_scope']='BrowserSession connection to prestarted Chromium; browser process launch excluded'
        probe=Path('/bench/probe.js').read_text()
        for i in range(3):
            page=await browser.new_page()
            t=time.perf_counter();await page.goto(sys.argv[1])
            for _ in range(100):
                try:
                    if decode(await page.evaluate('() => window.fixtureReady === true')) is True:break
                except Exception:pass
                await asyncio.sleep(.1)
            else:raise TimeoutError('fixtureReady did not become true')
            result['runs'].append({'navigation_ms':(time.perf_counter()-t)*1000,'checks':decode(await page.evaluate(probe))})
            if i==0:
                try:
                    field=(await page.get_elements_by_css_selector('#name'))[0];await field.fill('Lupa')
                    button=(await page.get_elements_by_css_selector('#go'))[0];await button.click()
                    result['interaction']=decode(await page.evaluate("() => document.querySelector('#greeting').textContent"))
                except Exception as e:result['interaction_error']=str(e)
                await page.evaluate("() => {document.querySelector('#name').value='';document.querySelector('#greeting').textContent=''}")
                t=time.perf_counter()
                try:
                    (output/'browser-use.png').write_bytes(base64.b64decode(await page.screenshot()))
                    result['screenshot']={'ok':True,'ms':(time.perf_counter()-t)*1000}
                except Exception as e:result['screenshot']={'ok':False,'error':str(e)}
                try:
                    session_id=await page.session_id
                    t=time.perf_counter();pdf=await browser.cdp_client.send.Page.printToPDF({'printBackground':True},session_id=session_id)
                    (output/'browser-use.pdf').write_bytes(base64.b64decode(pdf['data']))
                    result['pdf']={'ok':True,'ms':(time.perf_counter()-t)*1000,'via':'BrowserSession CDP'}
                except Exception as e:result['pdf']={'ok':False,'error':str(e)}
            await browser.close_page(page)
    except Exception:result['error']=traceback.format_exc()
    finally:
        if browser:await browser.kill()
        try:os.killpg(process.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.kill();process.wait()
        profile.cleanup()
        (output/'browser-use.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
asyncio.run(main())
