#!/usr/bin/env python3
"""Verify targeted substitution with native CLI tools and a synthetic model.

The OS denies every network connection. All tools operate on temporary fixtures;
the user account, projects, remote commands, and real credentials are untouched.
"""

import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
from synthetic_config import write_config
import threading
import time

ROOT = Path(__file__).resolve().parent
PRODUCTION = ROOT.parent / 'plugins/my-privacy'

MODEL = r'''
import {CALLS, EXPECTED, REPORT, FOLLOWUP, RESUMED, SESSION} from './paths.js';
const captures=[];
const observed=[];
let initialDone=false;
function result(e,answer,tools=[],stop='end_turn') {
  return {turnId:e.turnId,index:e.index,answer,toolUses:tools,stopReason:stop,usage:null};
}
function facts(messages) {
  const inputs=messages.flatMap(m=>Array.isArray(m.content)?m.content.filter(b=>b.type==='tool_use').map(b=>b.input):[]);
  const text=JSON.stringify(inputs);
  return {rawPinnedArgumentsPresent:/chenxinghe|Cedarbyte/.test(text),
    arbitraryEmailPreserved:text.includes('other.person@example.test'),
    genericPiiTokensAbsent:!text.includes('<PII_'),nativeCallCount:observed.length};
}
export function register(on) {
  on('tool.call',async($,e,next)=>{
    const expected=EXPECTED[observed.length];
    observed.push({expectedTool:e.tool===expected?.name,
      preparedArgumentsMatch:!!expected&&Object.entries(expected.input).every(([key,value])=>e[key]===value)});
    return next(e);
  });
  on('turn.step',async function*($,e){
    const messages=await $.session.messages({as:'api'});
    if(JSON.stringify(messages.at(-1)).includes('OFFLINE_TARGETED_RESUME')) {
      await $.fs.write(RESUMED,JSON.stringify({modelReached:true,...facts(messages)}));
      yield {kind:'text',index:0,text:'OFFLINE_TARGETED_RESUME_COMPLETE'};
      yield {kind:'stop',stopReason:'end_turn',usage:null};
      return result(e,'OFFLINE_TARGETED_RESUME_COMPLETE');
    }
    if(initialDone) {
      await $.fs.write(FOLLOWUP,JSON.stringify({modelReached:true,...facts(messages)}));
      yield {kind:'text',index:0,text:'OFFLINE_TARGETED_FOLLOWUP_COMPLETE'};
      yield {kind:'stop',stopReason:'end_turn',usage:null};
      return result(e,'OFFLINE_TARGETED_FOLLOWUP_COMPLETE');
    }
    const tools=messages.flatMap(m=>Array.isArray(m.content)?m.content.filter(b=>b.type==='tool_result'):[]);
    const last=tools.at(-1);
    const text=last?JSON.stringify(last.content):'';
    if(e.index>0)captures.push({resultExists:!!last,isError:last?.is_error===true,
      genericEmailVisible:text.includes('other.person@example.test'),
      phoneAndCardVisible:text.includes('+1 202-555-0147')&&text.includes('4111111111111111'),
      shortIdentifiersVisible:text.includes('cxh rc'),
      aliasesVisible:/ryanchen|Harborwave|陈瑞恩|海岚数科/.test(text),
      accountAliasVisible:text.includes('ryanchen@harborwave.com'),
      originalsAbsent:!/chenxinghe|cedarbyte|陈星河|云杉智科/i.test(text),
      piiTokenAbsent:!text.includes('<PII_'),
      schemaMismatch:text.includes('does not match its output shape'),
      nativeFailureExplained:text.includes('OFFLINE_NATIVE_FAILURE'),
      missingFileExplained:/does not exist|No such file|not found|not exist/i.test(text),
      privacyGuardDenial:/(?:Local privacy|MyPrivacy) guard withheld|matching local privacy rules|private original values/.test(text)});
    const call=CALLS[e.index];
    if(!call) {
      initialDone=true;
      await $.fs.write(SESSION,await $.session.id());
      await $.fs.write(REPORT,JSON.stringify({completed:true,captures,observed,...facts(messages)}));
      yield {kind:'text',index:0,text:'OFFLINE_TARGETED_INITIAL_COMPLETE'};
      yield {kind:'stop',stopReason:'end_turn',usage:null};
      return result(e,'OFFLINE_TARGETED_INITIAL_COMPLETE');
    }
    yield {kind:'tool',index:0,id:`toolu_targeted_${e.index}`,name:call.name};
    yield {kind:'input',index:0,json:JSON.stringify(call.input)};
    yield {kind:'stop',stopReason:'tool_use',usage:null};
    return result(e,'',[call],'tool_use');
  });
}
'''

IDENTITY_MODEL = r'''
import {COMMAND, PAYLOAD, REPORT} from './paths.js';
let observed=0;
let argumentsUnchanged=true;
export function register(on) {
  on('tool.call',async($,e,next)=>{
    observed++;
    argumentsUnchanged=argumentsUnchanged&&e.tool==='Bash'&&e.command===COMMAND;
    return next(e);
  });
  on('turn.step',async function*($,e){
    if(e.index===0) {
      const call={name:'Bash',input:{command:COMMAND}};
      yield {kind:'tool',index:0,id:'toolu_identity',name:'Bash'};
      yield {kind:'input',index:0,json:JSON.stringify(call.input)};
      yield {kind:'stop',stopReason:'tool_use',usage:null};
      return {turnId:e.turnId,index:e.index,answer:'',toolUses:[call],stopReason:'tool_use',usage:null};
    }
    const messages=await $.session.messages({as:'api'});
    const rows=messages.flatMap(m=>Array.isArray(m.content)?m.content.filter(b=>b.type==='tool_result'):[]);
    const last=rows.at(-1);
    const text=JSON.stringify(last?.content);
    await $.fs.write(REPORT,JSON.stringify({modelReached:true,nativeCallCount:observed,
      argumentsUnchanged,resultSucceeded:!!last&&last.is_error!==true,
      noImplicitReplacement:!!text&&text.includes(PAYLOAD)}));
    yield {kind:'text',index:0,text:'OFFLINE_CONFIG_IDENTITY_COMPLETE'};
    yield {kind:'stop',stopReason:'end_turn',usage:null};
    return {turnId:e.turnId,index:e.index,answer:'OFFLINE_CONFIG_IDENTITY_COMPLETE',toolUses:[],stopReason:'end_turn',usage:null};
  });
}
'''


def read_json(path):
    return json.loads(path.read_text()) if path.is_file() else {}


def restore(value):
    for alias,original in [('陈瑞恩','陈星河'),('ryanchen','chenxinghe'),('海岚数科','云杉智科'),('Harborwave','Cedarbyte'),('harborwave','cedarbyte')]:
        value=value.replace(alias,original)
    return value


def verify_unconfigured_modes(workspace, plugin, cli, base_env):
    """Explicit empty, malformed, or absent files must not select real mappings."""
    cases={}
    payload='陈星河 chenxinghe ChenXingHe 云杉智科 Cedarbyte 陈瑞恩 ryanchen 海岚数科 harborwave other.person@example.test cxh rc'
    for name,content in [('empty', '{"mappings":[]}'), ('malformed', '{"mappings":'), ('unavailable', None)]:
        directory=workspace/name;directory.mkdir(mode=0o700)
        config=directory/'config';config.mkdir(mode=0o700)
        mappings=directory/'private-mappings.json'
        if content is not None:mappings.write_text(content)
        model=directory/'model';(model/'.claude-plugin').mkdir(parents=True);(model/'hooks').mkdir()
        (model/'.claude-plugin/plugin.json').write_text(json.dumps({'name':'offline-config-model','version':'0.1.0','description':'Synthetic empty and invalid configuration verification'}))
        (model/'hooks/hooks.json').write_text('{"modules":["./register.js"]}')
        (model/'hooks/register.js').write_text(IDENTITY_MODEL)
        command=f'printf "%s\\n" "{payload}" > identity.txt; cat identity.txt'
        values={'COMMAND':command,'PAYLOAD':payload,'REPORT':str(directory/'result.json')}
        (model/'hooks/paths.js').write_text(''.join('export const '+key+'='+json.dumps(value)+';\n' for key,value in values.items()))
        env=dict(base_env,CLAUDE_CONFIG_DIR=str(config),CLAUDE_MY_PRIVACY_CONFIG=str(mappings))
        invocation=['/usr/bin/sandbox-exec','-p','(version 1)(allow default)(deny network*)',cli,
            '--setting-sources','','--strict-mcp-config','--mcp-config','{"mcpServers":{}}',
            '--dangerously-skip-permissions','--tools','Bash','--plugin-dir',str(plugin),'--plugin-dir',str(model)]
        try:
            child=subprocess.run(invocation+['-p','OFFLINE_CONFIG_IDENTITY'],cwd=directory,env=env,
                capture_output=True,text=True,timeout=35,check=False)
            case=read_json(directory/'result.json')
            case['processCompleted']=child.returncode==0 and 'OFFLINE_CONFIG_IDENTITY_COMPLETE' in child.stdout
            case['localFileUnchanged']=(directory/'identity.txt').is_file() and (directory/'identity.txt').read_text()==payload+'\n'
            # Commands are handled locally without a model request.
            status=subprocess.run(invocation+['-p','/my-privacy-status'],cwd=directory,env=env,
                capture_output=True,text=True,timeout=20,check=False)
            expected='loaded' if name=='empty' else 'invalid' if name=='malformed' else 'unavailable'
            case['configurationStatusCorrect']=status.returncode==0 and f'Configuration: {expected}; mappings: 0.' in status.stdout
        except subprocess.TimeoutExpired:
            case={'timedOut':True}
        cases[name]=case
    return cases


def main():
    os.umask(0o077)
    report={'networkDenied':True,'syntheticFixturesOnly':True,'isolatedConfiguration':True,'passed':False}
    cli=shutil.which('claude')
    if sys.platform!='darwin' or not cli or not Path('/usr/bin/sandbox-exec').is_file():
        report['prerequisitesMissing']=True
    else:
        with tempfile.TemporaryDirectory(prefix='my-privacy-targeted-e2e-') as directory:
            workspace=Path(directory)
            project=workspace/'chenxinghe'/'project';project.mkdir(parents=True)
            alias=str(project).replace('/chenxinghe/','/ryanchen/')
            config=workspace/'config';config.mkdir(mode=0o700)
            plugin=workspace/'my-privacy';shutil.copytree(PRODUCTION,plugin)
            generic='other.person@example.test +1 202-555-0147 4111111111111111 cxh rc'
            source='Author: 陈瑞恩\nCompany: 海岚数科\nAccount: ryanchen@harborwave.com\nGeneric: '+generic+'\n'
            heredoc=f'''cd {alias}; export CONTACT=ryanchen@harborwave.com; python3 - <<'PY'
import os
from pathlib import Path
text="陈瑞恩 海岚数科 " + os.environ["CONTACT"] + " other.person@example.test cxh rc"
Path("roundtrip.txt").write_text(text)
print(text)
PY
for n in 1 2; do printf '%s\\n' "$n"; done | tail -1'''
            calls=[
                {'name':'Bash','input':{'command':f'printf "%s\\n" "{generic}" > generic.txt; cat generic.txt'}},
                {'name':'Bash','input':{'command':'printf "%s\\n" "陈星河 chenxinghe 云杉智科 Cedarbyte" > originals.txt; cat originals.txt'}},
                {'name':'Bash','input':{'command':heredoc}},
                {'name':'Read','input':{'file_path':alias+'/roundtrip.txt'}},
                {'name':'Write','input':{'file_path':alias+'/created.txt','content':source}},
                {'name':'Edit','input':{'file_path':alias+'/created.txt','old_string':'Company: 海岚数科','new_string':'Company: Harborwave'}},
                {'name':'Read','input':{'file_path':alias+'/created.txt'}},
                {'name':'Bash','input':{'command':'printf "%s\\n" "OFFLINE_NATIVE_FAILURE chenxinghe Cedarbyte other.person@example.test"; exit 7'}},
                {'name':'Read','input':{'file_path':str(workspace/'native-missing.txt')}},
            ]
            expected=[{'name':call['name'],'input':{key:restore(value) for key,value in call['input'].items()}} for call in calls]
            model=workspace/'model';(model/'.claude-plugin').mkdir(parents=True);(model/'hooks').mkdir()
            (model/'.claude-plugin/plugin.json').write_text(json.dumps({'name':'offline-targeted-model','version':'0.1.0','description':'Synthetic targeted substitution verification'}))
            (model/'hooks/hooks.json').write_text('{"modules":["./register.js"]}')
            (model/'hooks/register.js').write_text(MODEL)
            values={'CALLS':calls,'EXPECTED':expected,'REPORT':str(workspace/'initial.json'),
                'FOLLOWUP':str(workspace/'followup.json'),'RESUMED':str(workspace/'resumed.json'),'SESSION':str(workspace/'session-id.txt')}
            (model/'hooks/paths.js').write_text(''.join('export const '+key+'='+json.dumps(value)+';\n' for key,value in values.items()))
            env={key:value for key,value in os.environ.items() if key in ('PATH','HOME','USER','LOGNAME','TMPDIR','LANG','LC_ALL','LC_CTYPE','TERM')}
            env.update({'CLAUDE_MY_PRIVACY_CONFIG': str(write_config(workspace)), 'CLAUDE_CONFIG_DIR':str(config),'ANTHROPIC_API_KEY':'offline-audit-placeholder',
                'DISABLE_TELEMETRY':'1','DISABLE_ERROR_REPORTING':'1','CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC':'1'})
            common=['/usr/bin/sandbox-exec','-p','(version 1)(allow default)(deny network*)',cli,
                '--setting-sources','','--strict-mcp-config','--mcp-config','{"mcpServers":{}}',
                '--dangerously-skip-permissions','--tools','Bash,Read,Write,Edit','--plugin-dir',str(plugin),'--plugin-dir',str(model)]
            process=subprocess.Popen(common+['-p','--input-format','stream-json','--output-format','stream-json','--verbose'],
                cwd=workspace,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
            events=queue.Queue();output=[];errors=[]
            def read_stream(stream,target,deliver=False):
                for line in stream:
                    target.append(line)
                    if deliver:
                        try:events.put(json.loads(line))
                        except ValueError:pass
            readers=[threading.Thread(target=read_stream,args=(process.stdout,output,True),daemon=True),
                threading.Thread(target=read_stream,args=(process.stderr,errors),daemon=True)]
            for reader in readers:reader.start()
            def send(text):
                process.stdin.write(json.dumps({'type':'user','message':{'role':'user','content':text},'parent_tool_use_id':None,'session_id':''})+'\n')
                process.stdin.flush()
            def wait_result(marker,limit=55):
                deadline=time.monotonic()+limit
                while time.monotonic()<deadline:
                    try:event=events.get(timeout=0.1)
                    except queue.Empty:
                        if process.poll() is not None:return False
                        continue
                    if event.get('type')=='result':return marker in str(event.get('result',''))
                return False
            try:
                send('OFFLINE_TARGETED_INITIAL: Exercise synthetic native tools.')
                report['initialCompleted']=wait_result('OFFLINE_TARGETED_INITIAL_COMPLETE')
                if report['initialCompleted']:
                    send('OFFLINE_TARGETED_FOLLOWUP: Continue with the existing tool history.')
                    report['followupCompleted']=wait_result('OFFLINE_TARGETED_FOLLOWUP_COMPLETE')
                process.stdin.close();process.wait(timeout=10)
            except (BrokenPipeError,subprocess.TimeoutExpired):report['timedOut']=True
            finally:
                if process.poll() is None:process.kill();process.wait(timeout=5)
                for reader in readers:reader.join(timeout=2)
            report['processSucceeded']=process.returncode==0
            report['moduleLoadError']='Failed to load' in ''.join(output+errors)
            report['initial']=read_json(workspace/'initial.json')
            report['followup']=read_json(workspace/'followup.json')
            report['localFiles']={
                'genericValuesUnchanged':(workspace/'generic.txt').is_file() and (workspace/'generic.txt').read_text()==generic+'\n',
                'rawOriginalArgumentsExecuted':(workspace/'originals.txt').is_file() and (workspace/'originals.txt').read_text()=='陈星河 chenxinghe 云杉智科 Cedarbyte\n',
                'heredocFullyRestored':(project/'roundtrip.txt').is_file() and (project/'roundtrip.txt').read_text()=='陈星河 云杉智科 chenxinghe@cedarbyte.com other.person@example.test cxh rc',
                'writeAndEditRestored':(project/'created.txt').is_file() and (project/'created.txt').read_text()==restore(source).replace('Company: 云杉智科','Company: Cedarbyte'),
                'aliasDirectoryNotCreated':not Path(alias).exists(),
            }
            if (workspace/'session-id.txt').is_file():
                session_id=(workspace/'session-id.txt').read_text()
                resumed=subprocess.run(common+['--resume',session_id,'-p','OFFLINE_TARGETED_RESUME'],cwd=workspace,
                    env=env,capture_output=True,text=True,timeout=40,check=False)
                report['resumeCompleted']=resumed.returncode==0 and 'OFFLINE_TARGETED_RESUME_COMPLETE' in resumed.stdout
                report['resumed']=read_json(workspace/'resumed.json')
            report['configurationModes']=verify_unconfigured_modes(workspace,plugin,cli,env)
    initial=report.get('initial',{});rows=initial.get('captures',[]);observed=initial.get('observed',[])
    report['checks']={
        'allNineNativeCallsObservedOnce':len(observed)==9 and all(row.get('expectedTool') for row in observed),
        'allPreparedArgumentsMatchRestoration':bool(observed) and all(row.get('preparedArgumentsMatch') for row in observed),
        'allNineToolResultsObserved':len(rows)==9 and all(row.get('resultExists') for row in rows),
        'firstSevenToolsSucceed':len(rows)==9 and all(not row.get('isError') for row in rows[:7]),
        'nativeErrorsRemainErrors':len(rows)==9 and rows[7].get('isError') and rows[8].get('isError'),
        'nativeFailureExplanationsSurvive':len(rows)==9 and rows[7].get('nativeFailureExplained') and rows[8].get('missingFileExplained'),
        'noOutputSchemaFailures':bool(rows) and all(not row.get('schemaMismatch') for row in rows),
        'noPrivacyPolicyDenials':bool(rows) and all(not row.get('privacyGuardDenial') for row in rows),
        'returnedOutputHasOnlyTargetedReplacements':bool(rows) and all(row.get('originalsAbsent') and row.get('piiTokenAbsent') for row in rows),
        'genericEmailPhoneAndCardUnchanged':len(rows)==9 and rows[0].get('genericEmailVisible') and rows[0].get('phoneAndCardVisible'),
        'shortIdentifiersUnchanged':len(rows)==9 and rows[0].get('shortIdentifiersVisible'),
        'companyAccountAliasVisible':len(rows)==9 and rows[2].get('accountAliasVisible') and rows[6].get('accountAliasVisible'),
        'rawPinnedHistoryDoesNotBlockNextTurn':report.get('followupCompleted',False) and report.get('followup',{}).get('rawPinnedArgumentsPresent',False),
        'nextTurnDoesNotReplayTools':report.get('followup',{}).get('nativeCallCount')==9,
        'resumedSessionDoesNotBlock':report.get('resumeCompleted',False) and report.get('resumed',{}).get('modelReached',False),
        'resumeDoesNotReplayTools':report.get('resumed',{}).get('nativeCallCount')==0,
        **report.get('localFiles',{}),
    }
    for name in ('empty','malformed','unavailable'):
        case=report.get('configurationModes',{}).get(name,{})
        report['checks'][name+'ConfigurationKeepsToolsWorking']=case.get('processCompleted',False) and case.get('resultSucceeded',False) and case.get('nativeCallCount')==1
        report['checks'][name+'ConfigurationHasNoImplicitMappings']=case.get('argumentsUnchanged',False) and case.get('noImplicitReplacement',False) and case.get('localFileUnchanged',False)
        report['checks'][name+'ConfigurationStatusCorrect']=case.get('configurationStatusCorrect',False)
    report['passed']=bool(report.get('processSucceeded')) and all(report['checks'].values())
    (ROOT/'evidence'/'targeted-latest-summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return 0 if report['passed'] else 1


if __name__=='__main__':sys.exit(main())
