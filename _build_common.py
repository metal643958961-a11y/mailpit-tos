"""Build deterministic next-version packages with shared regression rules."""
import configparser,gzip,hashlib,io,json,re,subprocess,sys,tarfile
from pathlib import Path
from xml.etree import ElementTree

def build(root):
 src=root/'package';c=json.loads((src/'config.ini').read_text());app=c['id']
 files=sorted(['config.ini','docker-compose.yml',app+'.lang',app+'.svg'])
 assert sorted(p.name for p in src.iterdir())==files,'four-file structure'
 assert all((src/f).is_file() and not (src/f).is_symlink() for f in files),'regular files only'
 assert c['category']==['Utilities'] and c['beta'] is False,'C17/V11'
 assert c['application_type']=='docker' and c['platform']=='x86_64' and c['depend']==['DockerEngine'],'type/architecture'
 y=json.loads(subprocess.check_output(['ruby','-ryaml','-rjson','-e','puts JSON.generate(YAML.safe_load(File.read(ARGV[0])))',str(src/'docker-compose.yml')]))
 assert (not y.get('volumes')) if app=='victoriametrics' else y['volumes']=={'state':{'driver':'local'}},'mount declaration'
 mount='/data' if app=='victoriametrics' else 'state'
 for name,s in y['services'].items():
  assert s['platform']=='linux/amd64' and s['user']==c['user'] and not s['user'].startswith('0:'),'non-root amd64'
  assert re.search(r'@sha256:[a-f0-9]{64}$',s['image']) and not re.search(r':[^@]*(?:rc|beta|alpha)',s['image']),'stable locked image'
  assert not s.get('privileged') and not s.get('network_mode') and not s.get('devices'),'host isolation'
  assert s['read_only'] and s['cap_drop']==['ALL'] and s['security_opt']==['no-new-privileges:true'],'hardening'
  assert s['volumes']==([mount+':/tmp'] if name=='initialize' else [mount+':/state']),'D16/scope'
  assert not re.search(r'(?<!\$)\$\{[^}]*:\?',json.dumps(s)),'uninitialized mandatory environment'
 if app=='inspircd':assert '127.0.0.1' in y['services'][app]['healthcheck']['test'][-1],'IPv4 healthcheck'
 lang=configparser.ConfigParser();lang.read(src/(app+'.lang'))
 assert len(lang.sections())==26 and all(json.loads(lang[s][k]).strip() for s in lang.sections() for k in ['name','auth','descript']),'translations'
 assert not re.search(r'\b(?:beta|alpha|rc[0-9]*)\b',(src/(app+'.lang')).read_text(),re.I),'V11 release notes'
 assert ElementTree.parse(src/(app+'.svg')).getroot().tag=='{http://www.w3.org/2000/svg}svg','SVG'
 assert (root/'PRIVACY.md').is_file() and (root/'README.md').is_file() and any((root/'licenses').iterdir()),'submission documents'
 stream=io.BytesIO()
 with gzip.GzipFile(fileobj=stream,mode='wb',mtime=0) as gz,tarfile.open(fileobj=gz,mode='w') as t:
  for f in files:
   raw=(src/f).read_bytes();info=tarfile.TarInfo(f);info.mode=0o644;info.size=len(raw);t.addfile(info,io.BytesIO(raw))
 out=root/'dist';out.mkdir(exist_ok=True);name=app+'.tar.gz';payload=stream.getvalue();(out/name).write_bytes(payload)
 digest=hashlib.sha256(payload).hexdigest();(out/'SHA256SUMS').write_text(digest+'  '+name+'\n');print('PASS',app,c['version'],digest)
if __name__=='__main__':
 for app in sys.argv[1:] or ['nats','mailpit','inspircd','victoriametrics']:build(Path(__file__).resolve().parent/app)
