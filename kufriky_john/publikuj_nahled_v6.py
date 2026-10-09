"""Copy only authorized static preview; read it back with public GET requests."""
from pathlib import Path
import concurrent.futures,hashlib,json,shutil,subprocess,time,urllib.request
ROOT=Path(__file__).resolve().parent
SITE=ROOT/'nahled-modely-v6'
DEST=Path('/opt/konfigurator/webapp/nahled-john/kufriky-milwaukee-modely-v6')
BASE='https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v6/'
OUT=ROOT/'overeni-tvar-v6'
allowed={'.html','.js','.css','.json','.csv','.glb','.png'}
files=[p for p in SITE.rglob('*') if p.is_file()]
for p in files:
 assert p.suffix in allowed,p
 if p.suffix in {'.html','.js','.css','.json','.csv'}:
  text=p.read_text(encoding='utf-8-sig')
  assert not any(x in text for x in ['/home/openai1','/opt/','ukoly/']),p
 if p.suffix=='.html':
  assert '<meta name="robots" content="noindex, nofollow">' in text,p
  assert '<iframe' not in text and '<img src="http' not in text,p
assert not DEST.exists(),'This script creates v6 only once; existing previews must be preserved.'
DEST.mkdir()
manifest=[]
for p in files:
 relative=p.relative_to(SITE);target=DEST/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
 sha=hashlib.sha256(p.read_bytes()).hexdigest();assert hashlib.sha256(target.read_bytes()).hexdigest()==sha
 manifest.append(dict(file=str(relative),bytes=p.stat().st_size,sha256=sha))
(OUT/'nahrani.json').write_text(json.dumps(dict(files=len(manifest),bytes=sum(r['bytes'] for r in manifest),rows=manifest),ensure_ascii=False,indent=2)+'\n')
curl=subprocess.run(['curl','--silent','--show-error','--location','--max-time','30','--output','/dev/null','--write-out','%{http_code}',BASE],capture_output=True,text=True)
assert curl.returncode==0 and curl.stdout=='200',(curl.returncode,curl.stdout)
def read(row):
 for attempt in range(3):
  try:
   request=urllib.request.Request(BASE+row['file'],headers={'User-Agent':'John-static-preview-read-check'})
   with urllib.request.urlopen(request,timeout=25) as response:
    body=response.read();status=response.status
   actual=hashlib.sha256(body).hexdigest()
   return dict(file=row['file'],http_status=status,sha256_matches=actual==row['sha256'])
  except Exception as e:
   if attempt==2:return dict(file=row['file'],error=str(e))
   time.sleep(.5)
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(read,manifest))
errors=[r for r in results if r.get('http_status')!=200 or not r.get('sha256_matches')]
(OUT/'verejne-cteni.json').write_text(json.dumps(dict(status='FAIL' if errors else 'PASS',curl_http=200,files=len(results),rows=results,errors=errors),ensure_ascii=False,indent=2)+'\n')
print('Veřejný náhled:',len(results),'statických souborů; HTTP 200 + shodné SHA-256:',len(results)-len(errors))
assert not errors,errors[:5]
