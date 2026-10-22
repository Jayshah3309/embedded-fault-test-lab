"""Deterministic fault injection into a real compiled C++ controller; no third-party packages."""
import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
HEADER = ROOT/'firmware/fault_demo/control.h'
DRIVER = ROOT/'host/driver.cpp'
STATES = {'BOOT','READY','ACTIVE','STOPPED','FAULT'}
STEP_KEYS = {'time_ms','fresh','valid','value','stop_closed','command','expect'}
MUTATIONS = {
    'missing-stale-check': ('if (age(now,lastSample_) >= SENSOR_TIMEOUT_MS)', 'if (false)'),
    'missing-heartbeat-check': ('if (state_ == ACTIVE && (!hasHeartbeat_ || age(now,lastHeartbeat_) >= HEARTBEAT_TIMEOUT_MS))', 'if (false)'),
    'missing-threshold-trip': ('if (value_ >= TRIP_VALUE)', 'if (false)'),
}


def digest(data): return hashlib.sha256(data).hexdigest()


def load_scenarios(path):
    raw = Path(path).read_bytes()
    if len(raw)>2_000_000: raise ValueError('scenario file exceeds 2 MB')
    data = json.loads(raw)
    if not isinstance(data,dict) or set(data)!={'schema_version','scenarios'} or type(data['schema_version']) is not int or data['schema_version']!=1:
        raise ValueError('expected schema_version 1 and scenarios')
    cases = data['scenarios']
    if not isinstance(cases,list) or not 1<=len(cases)<=100: raise ValueError('expected 1..100 scenarios')
    names=set()
    for case in cases:
        if not isinstance(case,dict) or set(case)!={'name','purpose','steps'}: raise ValueError('invalid scenario fields')
        name=case['name']
        if not isinstance(name,str) or not re.fullmatch(r'[a-z0-9-]{1,80}',name) or name in names: raise ValueError('invalid or duplicate scenario name')
        names.add(name)
        if not isinstance(case['purpose'],str) or len(case['purpose'])>500: raise ValueError('invalid purpose')
        if not isinstance(case['steps'],list) or not 1<=len(case['steps'])<=10000: raise ValueError('expected 1..10000 steps')
        for step in case['steps']:
            if not isinstance(step,dict) or set(step)!=STEP_KEYS: raise ValueError('invalid step fields')
            for key in ('fresh','valid','stop_closed'):
                if type(step[key]) is not bool: raise ValueError('boolean required: '+key)
            if type(step['time_ms']) is not int or not 0<=step['time_ms']<=0xffffffff: raise ValueError('invalid uint32 time')
            if type(step['value']) is not int or not -32768<=step['value']<=32767: raise ValueError('invalid int16 value')
            cmd=step['command']
            if not isinstance(cmd,str) or len(cmd)!=1 or not 33<=ord(cmd)<=126: raise ValueError('command must be one printable ASCII byte')
            expected=step['expect']
            if not isinstance(expected,dict) or not {'state','permit','faults'}<=set(expected)<= {'state','permit','faults','healthy_samples'}: raise ValueError('invalid expectation fields')
            if not isinstance(expected['state'],str) or expected['state'] not in STATES or type(expected['permit']) is not bool: raise ValueError('invalid expected state/permit')
            if type(expected['faults']) is not int or not 0<=expected['faults']<=255: raise ValueError('invalid expected faults')
            if 'healthy_samples' in expected and (type(expected['healthy_samples']) is not int or not 0<=expected['healthy_samples']<=3): raise ValueError('invalid expected healthy count')
    return cases, digest(raw)


def build(binary, cxx='g++', header_dir=None, sanitize=False):
    binary=Path(binary)
    binary.parent.mkdir(parents=True,exist_ok=True)
    command=[cxx,'-std=c++11','-Wall','-Wextra','-Werror','-pedantic','-g','-O1']
    if sanitize: command+=['-fsanitize=undefined','-fno-sanitize-recover=all']
    command+=['-I',str(header_dir or HEADER.parent),str(DRIVER),'-o',str(binary)]
    subprocess.run(command,check=True,capture_output=True,text=True,timeout=60)
    return command


def run_scenario(binary, case):
    lines=['{time_ms} {fresh:d} {valid:d} {value} {stop_closed:d} {command}'.format(**step) for step in case['steps']]
    result=subprocess.run([str(Path(binary).resolve())],input='\n'.join(lines)+'\n',text=True,capture_output=True,timeout=10)
    errors=[]
    try:
        actual=[json.loads(line) for line in result.stdout.splitlines()]
    except ValueError:
        actual=[];errors.append('driver emitted invalid JSON')
    if result.returncode:errors.append('driver exit '+str(result.returncode)+': '+result.stderr[:1000])
    if len(actual)!=len(case['steps']):errors.append(f"expected {len(case['steps'])} trace rows; received {len(actual)}")
    trace=[]
    for index,step in enumerate(case['steps']):
        observed=actual[index] if index<len(actual) else {}
        mismatches=[]
        if not isinstance(observed,dict):observed={};mismatches.append('trace must be an object')
        if observed.get('time_ms')!=step['time_ms']:mismatches.append('time_ms mismatch')
        for key,expected in step['expect'].items():
            value=observed.get(key)
            if type(value)!=type(expected) or value!=expected:
                mismatches.append(f'{key}: expected {expected!r}, got {value!r}')
        # Independent invariant, beyond the hand-authored expected state.
        if observed.get('permit') and (observed.get('faults')!=0 or observed.get('state')!='ACTIVE'):
            mismatches.append('permit asserted outside fault-free ACTIVE state')
        errors += [f'step {index}: '+message for message in mismatches]
        trace.append(dict(input={k:v for k,v in step.items() if k!='expect'},expected=step['expect'],actual=observed,errors=mismatches))
    return dict(name=case['name'],purpose=case['purpose'],passed=not errors,errors=errors,trace=trace)


def evaluate(binary,cases): return [run_scenario(binary,case) for case in cases]


def write_reports(out, report):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    results=report['results'];failed=sum(not r['passed'] for r in results)
    suite=ET.Element('testsuite',name='embedded-fault-test-lab',tests=str(len(results)),failures=str(failed))
    cards=[]
    for result in results:
        case=ET.SubElement(suite,'testcase',name=result['name'],classname='faultlab.scenarios')
        if not result['passed']:ET.SubElement(case,'failure',message='scenario failed').text='\n'.join(result['errors'])
        trace=json.dumps(result['trace'],indent=2)
        ET.SubElement(case,'system-out').text=trace
        status='PASS' if result['passed'] else 'FAIL'
        cards.append('<details><summary><b>'+status+'</b> '+html.escape(result['name'])+'</summary><p>'+html.escape(result['purpose'])+'</p><pre>'+html.escape(trace)+'</pre></details>')
    ET.ElementTree(suite).write(out/'junit.xml',encoding='utf-8',xml_declaration=True)
    document='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Fault Lab report</title><style>body{font-family:system-ui;background:#101b24;color:#eaf1f5;max-width:1000px;margin:auto;padding:32px}p,small{color:#b6c9d7}details{background:#1b2c38;border:1px solid #365164;border-radius:8px;padding:16px;margin:12px 0}summary{cursor:pointer}b{color:#79dfbf}pre{overflow:auto;font-size:12px}code{overflow-wrap:anywhere}</style><small>JAY SHAH / EMBEDDED SYSTEMS</small><h1>Embedded Fault Testing Lab</h1>'''
    document+=f'<h2>{len(results)-failed}/{len(results)} scenarios passed</h2><p>Host software simulation · not physical hardware certification</p><p>UTC: {html.escape(report["generated_at"])}<br>Core SHA-256: <code>{report["core_sha256"]}</code></p>'
    document+=''.join(cards)+'<footer><p>Virtual timestamps are test inputs, not measured response latency. See report.json for compiler and environment evidence.</p></footer></html>'
    (out/'report.html').write_text(document)


def mutation_check(cases,cxx,sanitize,out):
    mutations=[]
    source=HEADER.read_text()
    with tempfile.TemporaryDirectory() as tmp:
        directory=Path(tmp)
        for name,(before,after) in MUTATIONS.items():
            if source.count(before)!=1:raise ValueError('mutation anchor must occur exactly once: '+name)
            (directory/'control.h').write_text(source.replace(before,after))
            binary=directory/name
            build(binary,cxx,directory,sanitize)
            results=evaluate(binary,cases)
            caught=[r['name'] for r in results if not r['passed']]
            mutations.append(dict(name=name,detected=bool(caught),failing_scenarios=caught))
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    (out/'mutations.json').write_text(json.dumps(dict(mode='deliberately broken host-only temporary copies',results=mutations),indent=2)+'\n')
    return mutations


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenarios',type=Path,default=ROOT/'scenarios/regression.json')
    parser.add_argument('--out',type=Path,default=ROOT/'reports')
    parser.add_argument('--cxx',default=os.getenv('CXX','g++'))
    parser.add_argument('--sanitize',action='store_true',help='GCC/Clang UndefinedBehaviorSanitizer, fail on first error')
    parser.add_argument('--mutations',action='store_true',help='require detection of 3 deliberately broken host-only variants')
    args=parser.parse_args(argv)
    try:
        cases,scenario_hash=load_scenarios(args.scenarios)
        with tempfile.TemporaryDirectory() as tmp:
            binary=Path(tmp)/'controller'
            command=build(binary,args.cxx,sanitize=args.sanitize)
            results=evaluate(binary,cases)
        version=subprocess.run([args.cxx,'--version'],capture_output=True,text=True,check=True,timeout=5).stdout.splitlines()[0]
        report=dict(schema_version=1,mode='host-software-simulation',generated_at=datetime.now(timezone.utc).isoformat(),
                    core_sha256=digest(HEADER.read_bytes()),driver_sha256=digest(DRIVER.read_bytes()),
                    scenario_sha256=scenario_hash,compiler=version,build_command=command,
                    python=platform.python_version(),platform=platform.platform(),sanitized=args.sanitize,results=results)
        write_reports(args.out,report)
        failed=sum(not result['passed'] for result in results)
        for result in results:
            print(('PASS ' if result['passed'] else 'FAIL ')+result['name'])
            for error in result['errors']:print('  '+error)
        mutations=mutation_check(cases,args.cxx,args.sanitize,args.out) if args.mutations and not failed else []
        if args.mutations and failed:print('Mutation checks skipped: baseline scenarios must pass first')
        for mutation in mutations:print(('CAUGHT ' if mutation['detected'] else 'MISSED ')+mutation['name'])
        print(f'{len(results)-failed}/{len(results)} scenarios passed; reports: {args.out.resolve()}')
        return 1 if failed or any(not m['detected'] for m in mutations) else 0
    except (ValueError,OSError,subprocess.SubprocessError) as error:
        print('lab error: '+str(error),file=sys.stderr)
        if isinstance(error,subprocess.CalledProcessError):print(error.stderr,file=sys.stderr)
        return 2


if __name__=='__main__':sys.exit(main())
