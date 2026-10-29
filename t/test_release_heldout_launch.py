"""Observe harmless stand-ins, never an actual model, while testing launch and recovery."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent / 'recipes'))
import release_heldout_launch as launch
from test_release_heldout_inputs import prepared, completed, freeze, invocation_fixture


@pytest.mark.parametrize('change', ['model', 'generation', 'runtime', 'launcher', 'exe', 'args', 'parent', 'listener', 'client', 'returncode', 'cache'])
def test_invocation_cannot_be_replaced_by_a_model_label(completed, change):
    root, claim, values, _, _ = completed
    value = invocation_fixture(root, claim, values)
    bundle, panel, _, decoder, protocol, _ = values
    generation = launch.heldout.completed(root, claim, bundle, panel, decoder, protocol)
    if change == 'model': value['model_sha256_after'] = '0' * 64
    elif change == 'generation': value['generation_sha256'] = '0' * 64
    elif change == 'runtime': value['server_files_sha256'] = {}
    elif change == 'launcher': value['launcher_sources_sha256'] = {}
    elif change == 'exe': value['attempts'][0]['start']['server']['exe'] = '/different/server'
    elif change == 'args': value['attempts'][0]['start']['server']['command'][-1] = 'different'
    elif change == 'parent': value['attempts'][0]['client']['parent_pid'] = 999
    elif change == 'listener': value['attempts'][0]['start']['server_owned_listener'] = False
    elif change == 'client': value['attempts'][0]['client'] = None
    elif change == 'returncode': value['attempts'][0]['returncode'] = 1
    else: value['cache_sha256'] = {'a' * 64 + '.json': 'b' * 64}
    with pytest.raises(ValueError): launch.validate_invocation(value, claim, protocol, generation)


def test_local_environment_cannot_start_final_generation(prepared, tmp_path, monkeypatch):
    monkeypatch.delenv('DAWNR_REMOTE_COMPUTE', raising=False)
    bundle, _, _, decoder, protocol, paths = prepared
    with pytest.raises(ValueError, match='remote compute'):
        launch.run(bundle, decoder, protocol, paths, tmp_path / 'ready')


@pytest.fixture
def stand_in(prepared, tmp_path, monkeypatch):
    if sys.platform != 'linux' or not shutil.which('cc'):
        pytest.skip('the process-observation stand-in requires Linux and a C compiler')
    # A tiny HTTP health responder. It has no inference API or model-loading code.
    folder = tmp_path / 'server'; folder.mkdir()
    source = folder / 'health.c'
    source.write_text('''#include <arpa/inet.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
int main(int argc,char **argv) {
 int port=0; for(int i=1;i+1<argc;i++) if(!strcmp(argv[i],"--port")) port=atoi(argv[i+1]);
 int s=socket(AF_INET,SOCK_STREAM,0),one=1; setsockopt(s,SOL_SOCKET,SO_REUSEADDR,&one,sizeof(one));
 struct sockaddr_in a={0}; a.sin_family=AF_INET; a.sin_port=htons(port); a.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
 if(bind(s,(struct sockaddr*)&a,sizeof(a))||listen(s,4)) return 2;
 const char *reply="HTTP/1.1 200 OK\\r\\nContent-Length: 2\\r\\nConnection: close\\r\\n\\r\\n{}";
 for(;;) {int c=accept(s,0,0); if(c<0) return 3; char buf[4096]; read(c,buf,sizeof(buf)); write(c,reply,strlen(reply));close(c);}
}
''')
    subprocess.run(['cc', str(source), '-o', str(folder / 'llama-server')], check=True, capture_output=True)
    bundle, panel, _, decoder, protocol, _ = deepcopy(prepared)
    root = tmp_path / 'execution'; (root / 't/recipes').mkdir(parents=True)
    (root / 't/spec_first.py').write_text('# synthetic fixture; no inference or reference execution\n')
    driver = root / 't/recipes/v6_server_route.py'
    driver.write_text('''import hashlib,json,sys,time
from pathlib import Path
time.sleep(.2)
args=sys.argv[1:]; route=args[args.index('--')+1:]
get=lambda xs,k: xs[xs.index(k)+1]
root=Path.cwd(); tag=get(route,'--tag'); panel=Path(get(route,'--ids-file')); cache=Path(get(args,'--cache'))
identity=get(args,'--identity'); sources={'t/spec_first.py':hashlib.sha256((root/'t/spec_first.py').read_bytes()).hexdigest()}
protocol={'schema':1,'decoder':'llama.cpp-Q8_0','model':'dawnr-route','identity':identity,'route_args':route,
 'panel_sha256':hashlib.sha256(panel.read_bytes()).hexdigest(),'sources':sources,
 'driver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
 'seed_rule':'sha256(canonical_json([stage, messages]))[:8] & 0x7fffffff'}
(cache/'protocol.json').write_text(json.dumps(protocol))
body={'model':'dawnr-route','max_tokens':1024,'messages':[{'role':'user','content':'synthetic cache record'}]}
key=hashlib.sha256(json.dumps([identity,body],sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
path=cache/(key+'.json')
if not path.exists(): path.write_text(json.dumps({'identity':identity,'request':body,'response':{}}))
if (root/'fail-first').exists():
 (root/'fail-first').unlink(); sys.exit(7)
out=root/'t/out/spec-experiment'/tag; (out/'raw').mkdir(parents=True,exist_ok=True)
(out/'spec_first.json').write_text(json.dumps({'problems':182,'answered':0,
 'per_problem':{i:{'python':None,'taken':None} for i in panel.read_text().split()}}))
for name in ('python.jsonl','kept-specs.jsonl','scored-specs.jsonl'): (out/name).write_text('')
(cache/'completed.json').write_text(json.dumps(protocol))
''')
    model = tmp_path / 'fixture.gguf'; model.write_bytes(b'not a model' * 400)
    model_sha = launch.digest(model)
    data = bundle['seeds']['1']; data['export']['output'].update(sha256=model_sha, bytes=model.stat().st_size)
    data['generation_audit']['development_models'] = {k: model_sha for k in data['generation_audit']['development_models']}
    for key in ('precision_model_sha256', 'spec33_model_sha256'): data['generation_audit'][key] = model_sha
    freeze(bundle)
    panel_path = tmp_path / 'panel.txt'; panel_path.write_bytes(panel)
    ready = tmp_path / 'DEVELOPMENT_READY'; ready.write_text('synthetic readiness\n')
    paths = {'checkout': str(root), 'server_dir': str(folder), 'model': str(model), 'panel': str(panel_path)}
    decoder['sources'] = {'t/spec_first.py': launch.digest(root / 't/spec_first.py')}
    decoder['route_driver_sha256'] = launch.digest(driver)
    protocol['generation_registration_sha256'] = launch.heldout.choose.sha(launch.heldout.decoder_registration(decoder))
    protocol['launcher_sources_sha256'] = {name: launch.digest(Path(launch.__file__).parent / name) for name in launch.CONTROL_MODULES}
    protocol['server_files_sha256'] = launch.runtime_files(folder)
    # Only the absent fixture Git history is substituted. All file hashes and real process observations run.
    original = subprocess.check_output
    def git_revision(args, **kwargs):
        if args[0] == 'git': return protocol['execution_revision'] + '\n'
        return original(args, **kwargs)
    monkeypatch.setattr(subprocess, 'check_output', git_revision)
    monkeypatch.setenv('DAWNR_REMOTE_COMPUTE', '1')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0)); port = probe.getsockname()[1]
    monkeypatch.setattr(launch, 'PORT', port)
    return bundle, decoder, protocol, paths, ready


def test_real_process_observation_completes_once_and_reuses_receipt(stand_in):
    record = launch.run(*stand_in)
    assert record['attempts'][0]['status'] == 'completed' and len(record['cache_sha256']) == 1
    assert launch.run(*stand_in) == record
    assert len(list((Path(stand_in[3]['checkout']) / 't/out/laptop-runs').glob('private-heldout-*/attempt-*'))) == 1


def test_original_cache_survives_a_failed_client_and_explicit_resume(stand_in):
    root = Path(stand_in[3]['checkout']); (root / 'fail-first').touch()
    with pytest.raises(ValueError, match='decoder failed'): launch.run(*stand_in)
    with pytest.raises(ValueError, match='explicit same-cache'): launch.run(*stand_in)
    record = launch.run(*stand_in, resume=True)
    assert [a['status'] for a in record['attempts']] == ['failed', 'completed']
    assert record['attempts'][0]['cache_after'] == record['attempts'][1]['cache_after']


def test_completed_reading_recovers_its_receipt_without_another_invocation(stand_in):
    original = launch.run(*stand_in)
    root = Path(stand_in[3]['checkout']) / 't/out/laptop-runs'
    path, = root.glob('private-heldout-*/receipt.json'); path.unlink()
    assert launch.run(*stand_in, resume=True) == original
    assert len(list(root.glob('private-heldout-*/attempt-*'))) == 1


def test_completed_cache_corruption_cannot_trigger_another_generation(stand_in):
    launch.run(*stand_in)
    root = Path(stand_in[3]['checkout']) / 't/out/laptop-runs'
    path, = [p for p in root.glob('cache-*/*.json') if len(p.stem) == 64]
    record = json.loads(path.read_text()); record['response'] = {'changed': True}
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match='cache changed'): launch.run(*stand_in)
    assert len(list(root.glob('private-heldout-*/attempt-*'))) == 1


def test_busy_shared_gpu_cannot_create_a_generation_claim(stand_in):
    import fcntl
    root = Path(stand_in[3]['checkout']) / 't/out'; root.mkdir()
    with (root / '.laptop-gpu.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError): launch.run(*stand_in)
    assert not list(root.glob('laptop-runs/private-heldout-*/claim.json'))
