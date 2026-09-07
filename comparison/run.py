"""Rerun the local fixture checks against the existing comparison containers."""
import json,subprocess
from pathlib import Path

root=Path(__file__).resolve().parent
def docker(*args,**kwargs):
    return subprocess.run(['docker',*args],check=True,**kwargs)
def ip(name):
    return subprocess.check_output(['docker','inspect','--format','{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}',name],text=True).strip()

fixture=f'http://{ip("lupa-compare-base")}:8090/fixture.html'
results=root/'results';results.mkdir(exist_ok=True)
for name,entry in [('obscura','/devtools/browser'),('lightpanda','/')]:
    with (results/f'{name}.log').open('w') as log:
        docker('exec','lupa-compare-base','node','/bench/cdp.cjs',name,f'ws://{ip("lupa-compare-"+name)}:9222{entry}',fixture,stdout=log,stderr=subprocess.STDOUT,timeout=150)
for name in ['browser-use','scrapling']:
    docker('restart','-t','1','lupa-compare-'+name,stdout=subprocess.DEVNULL)
    with (results/f'{name}.log').open('w') as log:
        try:
            docker('exec','lupa-compare-'+name,'python',f'/bench/{name}-bench.py',fixture,stdout=log,stderr=subprocess.STDOUT,timeout=150)
        finally:
            docker('restart','-t','1','lupa-compare-'+name,stdout=subprocess.DEVNULL)
docker('exec','lupa-lupa-1','mkdir','-p','/tmp/lupa-comparison')
for name in ['probe.js','lupa-bench.js']:
    docker('cp',str(root/name),'lupa-lupa-1:/tmp/lupa-comparison/'+name)
with (results/'lupa.log').open('w') as log:
    docker('exec','lupa-lupa-1','/config/.bun/bin/bun','/tmp/lupa-comparison/lupa-bench.js',fixture,stdout=log,stderr=subprocess.STDOUT,timeout=150)
for name in ['lupa.json','lupa.png','lupa.pdf']:
    docker('cp','lupa-lupa-1:/tmp/lupa-comparison/'+name,str(results/name))
names=['lupa-lupa-1','lupa-compare-base','lupa-compare-browser-use','lupa-compare-scrapling','lupa-compare-obscura','lupa-compare-lightpanda']
# Select fields explicitly: docker inspect's Config.Env may contain API secrets.
inventory=[]
for name in names:
    obj=json.loads(subprocess.check_output(['docker','inspect',name]))[0]
    image=json.loads(subprocess.check_output(['docker','image','inspect',obj['Image']]))[0]
    inventory.append({'container':name,'image_id':obj['Image'],'digests':image.get('RepoDigests'), 'image_bytes':image['Size'],'memory_limit':obj['HostConfig']['Memory'],'nano_cpus':obj['HostConfig']['NanoCpus'],'state':obj['State']['Status']})
(results/'inventory.json').write_text(json.dumps(inventory,indent=2))
for name in ['base','browser-use','scrapling']:
    container='lupa-compare-'+name
    with (results/f'{name}-pip-freeze.txt').open('w') as f:
        docker('exec',container,'pip','freeze',stdout=f)
    with (results/f'{name}-chromium.txt').open('w') as f:
        docker('exec',container,'chromium','--version',stdout=f)
with (results/'base-npm.json').open('w') as f:
    docker('exec','lupa-compare-base','npm','ls','--prefix','/opt/client','--json',stdout=f)
with (results/'idle-stats.jsonl').open('w') as f:
    docker('stats','--no-stream','--format','{{json .}}',*names,stdout=f)
print('Results:',results)
