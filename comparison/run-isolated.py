"""Test one browser at a time, preserving Lupa's live session via pause."""
import datetime,json,subprocess,time,statistics
from pathlib import Path

root=Path(__file__).resolve().parent
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S')
out=root/'isolated-results'/stamp;out.mkdir(parents=True)
remote='/bench/isolated-results/'+stamp
names=['browser-use','scrapling','obscura','lightpanda']
def docker(*args,**kw):
    return subprocess.run(['docker',*args],check=True,**kw)
def ip(name):
    return subprocess.check_output(['docker','inspect','--format','{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}',name],text=True).strip()
def state():
    return subprocess.check_output(['docker','ps','-a','--format','{{.Names}} {{.Status}}'],text=True)
def test(name,command):
    print('START '+name,flush=True)
    (out/(name+'-containers.txt')).write_text(state())
    start=time.perf_counter()
    try:
        with (out/(name+'.log')).open('w') as log:
            docker(*command,stdout=log,stderr=subprocess.STDOUT,timeout=150)
    except Exception as e:
        (out/(name+'.json')).write_text(json.dumps({'name':name,'error':str(e),'runs':[]},indent=2))
    print('END '+name+' '+str(round(time.perf_counter()-start,1))+' s',flush=True)

paused=False
try:
    docker('stop','-t','1',*['lupa-compare-'+n for n in names],stdout=subprocess.DEVNULL)
    fixture=f'http://{ip("lupa-compare-base")}:8090/fixture.html'
    docker('exec','lupa-lupa-1','mkdir','-p','/tmp/lupa-comparison')
    for f in ['probe.js','lupa-bench.js']:
        docker('cp',str(root/f),'lupa-lupa-1:/tmp/lupa-comparison/'+f)
    test('lupa',['exec','lupa-lupa-1','/config/.bun/bin/bun','/tmp/lupa-comparison/lupa-bench.js',fixture])
    if not (out/'lupa.json').exists():
        for f in ['lupa.json','lupa.png','lupa.pdf']:
            docker('cp','lupa-lupa-1:/tmp/lupa-comparison/'+f,str(out/f))
    docker('pause','lupa-lupa-1',stdout=subprocess.DEVNULL);paused=True
    for name in names:
        container='lupa-compare-'+name
        docker('start',container,stdout=subprocess.DEVNULL)
        try:
            if name in ['browser-use','scrapling']:
                command=['exec','-e','BENCH_RESULTS='+remote,container,'python',f'/bench/{name}-bench.py',fixture]
            else:
                endpoint=f'ws://{ip(container)}:9222'+('/devtools/browser' if name=='obscura' else '/')
                time.sleep(1)
                command=['exec','-e','BENCH_RESULTS='+remote,'lupa-compare-base','node','/bench/cdp.cjs',name,endpoint,fixture]
            test(name,command)
        finally:
            docker('stop','-t','1',container,stdout=subprocess.DEVNULL)
finally:
    if paused:docker('unpause','lupa-lupa-1',stdout=subprocess.DEVNULL)
    (out/'final-containers.txt').write_text(state())

summary={}
for name in ['lupa',*names]:
    p=out/(name+'.json')
    d=json.loads(p.read_text()) if p.exists() else {'error':'No result','runs':[]}
    rows=d.get('runs',[])
    times=[r.get('request_ms',r.get('navigation_ms',r.get('navigation_to_ready_ms'))) for r in rows]
    ok=len(rows)==3 and all(r.get('checks',{}).get('js') and r['checks'].get('fetch') and r['checks'].get('cookie') and r['checks'].get('cards')==3 for r in rows) and d.get('interaction')=='Hola Lupa' and d.get('screenshot',{}).get('ok') and d.get('pdf',{}).get('ok')
    summary[name]={'pass':bool(ok),'samples_ms':times,'median_ms':statistics.median(times) if times else None,'error':d.get('error',d.get('errors',[]))}
(out/'summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2),flush=True)
print('OUTPUT '+str(out),flush=True)
