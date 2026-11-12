"""Guest-only regression. VM bind route explicitly models documented TOS mapping/chown; never claims real TOS."""
import re,base64,importlib.util,json,os,secrets,shutil,smtplib,subprocess,sys,tarfile,tempfile,time
from email.message import EmailMessage
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
app=sys.argv[1];package=Path(sys.argv[2]).resolve();legacy_path=Path(sys.argv[3]).resolve()
project='fix'+secrets.token_hex(5)
def check(ok,label):
 if not ok:raise RuntimeError(label)
 print('PASS',label,flush=True)
def cmd(*args):return subprocess.check_output(args,text=True).strip()
def wait(fn,label):
 for _ in range(60):
  try:
   if fn():check(True,label);return
  except (OSError,URLError,AssertionError,EOFError):pass
  time.sleep(.5)
 raise RuntimeError(label)
spec=importlib.util.spec_from_file_location('legacy',legacy_path);legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
check(os.geteuid()==0 and not cmd('docker','ps','-aq'),'dedicated empty Linux VM')
with tempfile.TemporaryDirectory(prefix=project) as tmp:
 root=Path(tmp)
 with tarfile.open(package) as t:(root/'docker-compose.yml').write_bytes(t.extractfile('docker-compose.yml').read())
 expected_uid=10000 if app=='inspircd' else 1000
 bind_mode=app=='victoriametrics' and b'/data:/state' in (root/'docker-compose.yml').read_bytes()
 if bind_mode:
  platform_data=root/'Volume2/DockerAppData'/app/'data'
  platform_data.mkdir(parents=True);os.chown(platform_data,expected_uid,expected_uid)
  (root/'unrelated-sentinel').write_text('leave unchanged')
  source=(root/'docker-compose.yml').read_text()
  (root/'docker-compose.yml').write_text(source.replace('/data:/tmp',str(platform_data)+':/tmp').replace('/data:/state',str(platform_data)+':/state'))
  print('PASS SIMULATED platform rewrites absolute /data under selected Volume2 and assigns configured UID; not developer manual preparation and not real TOS',flush=True)
 candidate_compose=(root/'docker-compose.yml').read_bytes()
 def compose(*args):return subprocess.check_output(['docker','compose','-p',project,*args],cwd=root,text=True).strip()
 def state():return json.loads(cmd('docker','inspect',app))[0]
 def http(path,password=None,data=None):
  port=18428 if app=='victoriametrics' else 18025;user='metrics' if app=='victoriametrics' else 'inbox'
  req=Request(f'http://127.0.0.1:{port}'+path,data=data)
  if password is not None:req.add_header('Authorization','Basic '+base64.b64encode((user+':'+password).encode()).decode())
  try:
   with urlopen(req,timeout=3) as r:return r.status,r.read()
  except HTTPError as e:return e.code,e.read()
 try:
  cfg=json.loads(compose('config','--format','json'))
  check(not (root/'.env').exists() and not (root/'data').exists(),'fresh install has no manual preparation')
  compose('create','--pull','never');compose('start')
  check(True,'clean volume cold start via compose create then start (cached images)')
  if bind_mode:private=platform_data/'private'
  else:
   volume=json.loads(cmd('docker','volume','inspect',project+'_state'))[0]
   private=Path(volume['Mountpoint'])/'private'
  password=(private/'password').read_text().strip()
  check(len(password)==64 and (private.stat().st_mode & 0o777)==0o700 and ((private/'password').stat().st_mode & 0o777)==0o600,'random credential and private directory permissions')
  expected_uid=10000 if app=='inspircd' else 1000
  check(private.stat().st_uid==expected_uid,'initializer writes as configured non-root UID')
  init_id=compose('ps','-aq','initialize');init=json.loads(cmd('docker','inspect',init_id))[0]
  check(init['Config']['User']==f'{expected_uid}:{expected_uid}' and init['State']['ExitCode']==0,'non-root initializer completed')
  sockets=[]
  def nats_ok():
   c=legacy.Client(password);ok=c.ok;c.close();return ok
  def irc_ok():
   c=legacy.client('probe'+secrets.token_hex(2),password);c[1].close();c[0].close();return True
  if app=='nats':
   wait(nats_ok,'first boot authenticates');bad=legacy.Client('wrong');check(not bad.ok,'wrong credentials refused');bad.close()
   c=legacy.Client(password);c.req('$JS.API.STREAM.CREATE.PILOT',json.dumps(dict(name='PILOT',subjects=['pilot.events'],storage='file',num_replicas=1)));check(c.req('pilot.events','synthetic')['seq']==1,'persistent message written');c.close()
   def retained():
    c=legacy.Client(password)
    try:return base64.b64decode(c.req('$JS.API.STREAM.MSG.GET.PILOT','{"seq":1}')['message']['data'])==b'synthetic'
    finally:c.close()
  elif app=='inspircd':
   wait(irc_ok,'first boot authenticates');bad=legacy.client('wrong','bad',False);bad[1].close();bad[0].close();check(True,'wrong IRC password refused')
   a=legacy.client('alpha',password);b=legacy.client('beta',password);sockets=[a,b]
   for c in sockets:c[2]('JOIN #pilot');c[3](' 366 ')
   a[2]('PRIVMSG #pilot :synthetic');b[3]('PRIVMSG #pilot :synthetic');check(True,'IRC channel message delivered')
   for c in sockets:c[1].close();c[0].close()
   sockets=[];wait(lambda:state()['State'].get('Health',{}).get('Status')=='healthy','IPv4 healthcheck is healthy')
   retained=irc_ok
  else:
   route='/api/v1/query?query=remediation_metric&nocache=1' if app=='victoriametrics' else '/api/v1/messages'
   wait(lambda:http(route,password)[0]==200,'first boot web/API login')
   check(http(route)[0]==401 and http(route,'wrong')[0]==401,'anonymous and wrong credentials refused')
   ui='/vmui/' if app=='victoriametrics' else '/';check(http(ui,password)[0]==200 and b'<script' in http(ui,password)[1],'web UI HTML and scripts available')
   if app=='victoriametrics':
    check(http('/api/v1/import/prometheus',password,b'remediation_metric 42\n')[0]==204,'metric written')
    def retained():return any(float(x['value'][1])==42 for x in json.loads(http(route,password)[1])['data']['result'])
   else:
    msg=EmailMessage();msg['From']='test@example.invalid';msg['To']='inbox@example.invalid';msg['Subject']='remediation-synthetic';msg.set_content('synthetic only')
    with smtplib.SMTP('127.0.0.1',11025,timeout=5) as smtp:smtp.send_message(msg)
    def retained():return any(x['Subject']=='remediation-synthetic' for x in json.loads(http(route,password)[1])['messages'])
   wait(retained,'API reads back synthetic data')
  logs=compose('logs','--no-color')
  check(password not in logs and base64.b64encode(('metrics:'+password).encode()).decode() not in logs,'generated credential absent from container logs')
  if app=='victoriametrics':
   for endpoint in ['/vmui/','/metrics','/api/v1/query?query=1','/api/v1/series?match[]=remediation_metric','/api/v1/export?match[]=remediation_metric']:
    check(http(endpoint)[0]==401,'unauthenticated endpoint denied '+endpoint)
   started=time.monotonic();ui_code,ui_body=http('/vmui/',password)
   scripts=re.findall(rb'<script[^>]+src="([^"]+)"',ui_body)
   check(ui_code==200 and scripts and time.monotonic()-started<5,'VMUI HTML under 5 seconds')
   for script in scripts:
    path=script.decode();path=path if path.startswith('/') else '/vmui/'+path
    check(http(path,password)[0]==200,'VMUI JavaScript asset served')
   for endpoint in ['/api/v1/admin/tsdb/delete_series?match[]=remediation_metric','/tags/delSeries?path=remediation_metric','/snapshot/create','/internal/force_flush','/internal/force_merge','/config','/-/reload','/flags','/debug/pprof/','/internal/log_new_series','/api/v1/admin/status/metric_names_stats/reset','/internal/resetRollupResultCache']:
    status,body=http(endpoint,data=b'')
    check(status in (401,403),'anonymous POST management endpoint denied '+endpoint+' status='+str(status))
   check(http('/api/v1/import/prometheus',password,b'rights_test_metric 7\n')[0]==204,'data rights synthetic import')
   wait(lambda:len(json.loads(http('/api/v1/query?query=rights_test_metric&nocache=1',password)[1])['data']['result'])==1,'data rights read channel')
   check(http('/api/v1/export?match[]=rights_test_metric',password)[0]==200,'data rights export channel')
   check(http('/api/v1/admin/tsdb/delete_series?match[]=rights_test_metric',password,b'')[0]==204,'authorized POST deletion channel works')
   wait(lambda:not json.loads(http('/api/v1/query?query=rights_test_metric&nocache=1',password)[1])['data']['result'],'deleted synthetic series no longer readable')
   logs=compose('logs','--no-color')
   check(password not in logs,'credential absent from logs after management requests')
  check(state()['HostConfig']['RestartPolicy']['Name']=='unless-stopped','automatic restart policy configured')
  cmd('systemctl','restart','docker')
  wait(lambda:state()['State']['Running'] and retained(),'Docker daemon restart recovers service and retained data')
  check((private/'password').read_text().strip()==password,'daemon restart preserves credential')
  s=state();check(s['Config']['User']==f'{expected_uid}:{expected_uid}' and s['HostConfig']['ReadonlyRootfs'] and 'ALL' in s['HostConfig']['CapDrop'],'main service non-root and hardened')
  image=json.loads(cmd('docker','image','inspect',s['Image']))[0];check(image['Os']=='linux' and image['Architecture']=='amd64','actual linux/amd64 image')
  started=time.monotonic();compose('stop');elapsed=time.monotonic()-started
  check(state()['State']['ExitCode']!=137 and elapsed<10,'graceful stop within 10 seconds')
  compose('start');wait(retained,'data or identity survives stop/start')
  compose('down');compose('up','-d','--pull','never');wait(retained,'data or identity survives remove/reinstall')
  check((private/'password').read_text().strip()==password,'reinitialization preserves credential')
  original=Path(sys.argv[4]).resolve() if len(sys.argv)>4 else None
  if original:
   compose('down')
   revised=(root/'docker-compose.yml').read_bytes()
   with tarfile.open(original) as t:(root/'docker-compose.yml').write_bytes(t.extractfile('docker-compose.yml').read())
   shutil.copytree(private/'data',root/'data');(root/'config').mkdir()
   (root/'config/http-password').write_text(password+'\n')
   if app=='mailpit':shutil.copy2(private/'auth.htpasswd',root/'config/auth.htpasswd')
   (root/'.env').write_text('IRC_SECRET='+password+'\nNATS_CLIENT_SECRET='+password+'\n');(root/'.env').chmod(0o600)
   for f in [root/'data',root/'config',*(root/'data').rglob('*'),*(root/'config').rglob('*')]:os.chown(f,expected_uid,expected_uid)
   compose('up','-d','--pull','never');wait(retained,'original release reads retained data with original bind layout')
   compose('down')
   shutil.rmtree(private/'data');shutil.copytree(root/'data',private/'data')
   for f in [private/'data',*(private/'data').rglob('*')]:os.chown(f,expected_uid,expected_uid)
   (root/'docker-compose.yml').write_bytes(revised);(root/'.env').unlink()
   compose('up','-d','--pull','never');wait(retained,'new release reads data migrated from stopped original release')
   check((private/'password').read_text().strip()==password,'migration preserves original credential')
  else:print('NOT_TESTED cross-version-bind-to-volume-migration',flush=True)
 finally:
  (root/'docker-compose.yml').write_bytes(candidate_compose)
  compose('down','--volumes','--remove-orphans')
  if bind_mode:
   check(platform_data.exists(),'SIMULATED clean=false retains bind data after compose down')
   assert platform_data.is_relative_to(root/'Volume2/DockerAppData'/app)
   shutil.rmtree(platform_data)
   check(not platform_data.exists() and (root/'unrelated-sentinel').read_text()=='leave unchanged','SIMULATED clean=true removes only mapped app data, preserves unrelated path')
 check(not cmd('docker','ps','-aq','--filter','label=com.docker.compose.project='+project) and not cmd('docker','volume','ls','-q','--filter','label=com.docker.compose.project='+project),'test containers and named volumes removed')
print('NOT_TESTED TOS App Center install/desktop/upgrade/uninstall',flush=True)
