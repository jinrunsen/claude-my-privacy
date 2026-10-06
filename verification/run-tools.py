#!/usr/bin/env python3
"""Run real Bash/Grep/Read tool regressions with a synthetic model and no network."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from synthetic_config import write_config

ROOT = Path(__file__).resolve().parent
PRODUCTION = ROOT.parent / "plugins/my-privacy"

MOCK = r'''
import {CALLS, REPORT} from './paths.js';
const captures=[];
function result(e,answer,tools=[],stop='end_turn'){return {turnId:e.turnId,index:e.index,answer,toolUses:tools,stopReason:stop,usage:null};}
export function register(on){
  on('turn.step',async function*($,e){
    const messages=await $.session.messages({as:'api'});
    const tools=messages.flatMap(m=>Array.isArray(m.content)?m.content.filter(b=>b.type==='tool_result'):[]);
    const last=tools[tools.length-1]; const text=last?JSON.stringify(last.content):'';
    if(e.index>0)captures.push({step:e.index-1,resultExists:!!last,isError:last?.is_error===true,withheld:text.includes('Local privacy guard'),permissionDenied:/permission|denied|not allowed|not permitted/i.test(text),toolUnavailable:/no such tool|not available|unknown tool|unrecognized tool|tool.+not found/i.test(text),listing:text.includes('fixture.js'),match:text.includes('bwg1'),hasNameAlias:text.includes('ryanchen.txt'),hasCompanyAlias:text.includes('Harborwave'),hasShortAlias:text.includes('rc'),hasSedMarker:text.includes('before.example.invalid'),unsupportedAliasCommand:text.includes('UNSUPPORTED_ALIAS_COMMAND'),complexAliasCommand:text.includes('COMPLEX_ALIAS_COMMAND'),notFound:/does not exist|not exist|No such file|not found|PATH_NOT_FOUND/i.test(text),missingPathCode:text.includes('PATH_NOT_FOUND'),rawVisible:text.includes('chenxinghe')||text.includes('Cedarbyte')});
    const call=CALLS[e.index];
    if(!call){await $.fs.write(REPORT,JSON.stringify({complete:true,captures}));yield {kind:'text',index:0,text:'OFFLINE_TOOL_AUDIT_COMPLETE'};yield {kind:'stop',stopReason:'end_turn',usage:null};return result(e,'OFFLINE_TOOL_AUDIT_COMPLETE');}
    yield {kind:'tool',index:0,id:`toolu_toolaudit_${e.index}`,name:call.name};
    yield {kind:'input',index:0,json:JSON.stringify(call.input)};
    yield {kind:'stop',stopReason:'tool_use',usage:null};
    return result(e,'',[call],'tool_use');
  });
}
'''


def instrument(plugin, diagnostics):
    path = plugin / 'hooks/register.js'
    text = path.read_text()
    text = 'const DIAGNOSTICS = ' + json.dumps(str(diagnostics)) + ';\nlet diagnosticRows=[];\n' + text
    if "let phase = 'prepare';" not in text:
        text = text.replace('let missing;', "let missing; let phase='prepare';")
    text = text.replace('if (privacy.containsProtected(argumentsOnly))', "let protectedArguments;\n    try { protectedArguments=privacy.containsProtected(argumentsOnly); } catch(error) { diagnosticRows.push({tool:event.tool,phase:'arguments',code:typeof error?.code==='string'?error.code:'NON_PRIVACY_ERROR',undefinedKeys:Object.keys(argumentsOnly).filter(k=>argumentsOnly[k]===undefined)}); await $.fs.write(DIAGNOSTICS,JSON.stringify(diagnosticRows)); throw error; }\n    if (protectedArguments)")
    text = text.replace('const answer = await next(ready);', "phase='next'; const answer = await next(ready); phase='rewrite';\n      diagnosticRows.push({tool:event.tool,phase:'result-shape',keys:Object.keys(answer),resultType:typeof answer.result,undefinedKeys:answer.result && typeof answer.result==='object'?Object.keys(answer.result).filter(k=>answer.result[k]===undefined):[]});\n      await $.fs.write(DIAGNOSTICS,JSON.stringify(diagnosticRows));")
    text = text.replace('} catch {\n      if (!missing)', "} catch (error) {\n      if (!missing) { diagnosticRows.push({tool:event.tool,phase,code:typeof error?.code==='string'?error.code:'NON_PRIVACY_ERROR'}); await $.fs.write(DIAGNOSTICS,JSON.stringify(diagnosticRows)); }\n      if (!missing)")
    text = text.replace('if (!missing) return toolFailure(phase, error);', "if (!missing) { diagnosticRows.push({tool:event.tool,phase,code:typeof error?.code==='string'?error.code:'NON_PRIVACY_ERROR'}); await $.fs.write(DIAGNOSTICS,JSON.stringify(diagnosticRows)); return toolFailure(phase,error); }")
    path.write_text(text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--diagnose', action='store_true', help='Instrument only a private temporary plugin copy.')
    parser.add_argument('--baseline', action='store_true', help='Temporarily restore the old undefined-field behavior and isolate tool-result regression.')
    parser.add_argument('--prefix-policy-baseline', type=Path, help='Use a private snapshot of the old shell policy for before-fix evidence.')
    parser.add_argument('--deny-bash', action='store_true', help='Check real native Bash denial with no permission-bypass option.')
    args = parser.parse_args()
    if sum(bool(option) for option in (args.baseline,args.prefix_policy_baseline,args.deny_bash))>1:
        parser.error('Baseline and native-denial modes cannot be combined.')
    os.umask(0o077)
    report = {'completed':False, 'networkDenied':True, 'syntheticFixturesOnly':True}
    with tempfile.TemporaryDirectory(prefix='my-privacy-tools-e2e-') as directory:
        workspace = Path(directory)
        fixture = workspace/'chenxinghe'/'project'
        fixture.mkdir(parents=True)
        (fixture/'fixture.js').write_text('const bwg1 = "example.invalid"; // Cedarbyte\n')
        (fixture/'chenxinghe.txt').write_text('Synthetic fixture only.\n')
        fixture_text = '// Synthetic fixture only.\n' * 17 + '\n'.join([
            'const target = "before.example.invalid";',
            'const shortAlias = "rc";',
            'const companyAlias = "Harborwave";',
            'const sourceCompany = "Cedarbyte";',
            'const name = "bwg1";',
            'const spare = "bwg2";',
            '// End of sed selection.',
        ]) + '\n'
        (fixture/'config.js').write_text(fixture_text)
        subprocess.run(['git','-c','init.defaultBranch=offline','init','--quiet',str(fixture)],check=True,capture_output=True)
        subprocess.run(['git','-C',str(fixture),'add','--intent-to-add','config.js'],check=True,capture_output=True)
        alias = str(fixture).replace('/chenxinghe/', '/ryanchen/')
        config = workspace/'config'; config.mkdir()
        plugin = workspace/'my-privacy'; shutil.copytree(PRODUCTION,plugin)
        if args.prefix_policy_baseline:
            shutil.copyfile(args.prefix_policy_baseline,plugin/'lib/tool-policy.js')
        if args.baseline:
            core=plugin/'lib/privacy.js'
            text=core.read_text()
            old='if (descriptor.value === undefined) continue;'
            if text.count(old)!=1: raise RuntimeError('Baseline fixture no longer matches production shape')
            core.write_text(text.replace(old,''))
            hook=plugin/'hooks/register.js'
            text=hook.read_text()
            marker="  on('turn.step',"
            if text.count(marker)!=1: raise RuntimeError('Baseline hook no longer matches production shape')
            # Isolate tool behavior under the old walker. The synthetic model
            # never uses a provider and the OS denies every network call.
            hook.write_text(text[:text.index(marker)]+'\n}\n')
        if args.diagnose or args.baseline: instrument(plugin,workspace/'diagnostics.json')
        mock = workspace/'mock'; (mock/'.claude-plugin').mkdir(parents=True); (mock/'hooks').mkdir()
        (mock/'.claude-plugin/plugin.json').write_text(json.dumps({'name':'offline-tool-audit','version':'0.1.0','description':'Offline synthetic tool regression'}))
        (mock/'hooks/hooks.json').write_text('{"modules":["./register.js"]}')
        (mock/'hooks/register.js').write_text(MOCK)
        calls = [
            {'name':'Bash','input':{'command':f'ls -a {alias}','description':'List synthetic project files'}},
            {'name':'Grep','input':{'pattern':'bwg','path':alias,'output_mode':'content'}},
            {'name':'Bash','input':{'command':f'cd {alias} && grep -rn bwg .','description':'Search synthetic project files'}},
            {'name':'Read','input':{'file_path':alias+'/src/index.js'}},
        ]
        # Keep the historic undefined-field baseline isolated to its four calls.
        if not args.baseline:
            calls.extend([
                {'name':'Bash','input':{'command':f'cd {alias} && sed -n 18,24p config.js','description':'Inspect the synthetic configuration'}},
                {'name':'Bash','input':{'command':f'''cd {alias} && python3 - <<'EOF'
from pathlib import Path
p = Path('config.js')
s = p.read_text()
assert 'const shortAlias = "rc";' in s
assert 'const companyAlias = "Harborwave";' in s
s = s.replace('before.example.invalid', 'after.example.invalid')
s = s.replace('const spare = "bwg2";\\n', '')
s += 'const scriptedAlias = "rc Harborwave";\\n'
p.write_text(s)
EOF
grep -n "bwg" config.js; ls; git diff --stat''','description':'Edit only a synthetic fixture with a Python heredoc'}},
            ])
        (mock/'hooks/paths.js').write_text('export const CALLS='+json.dumps(calls)+';\nexport const REPORT='+json.dumps(str(workspace/'audit.json'))+';\n')
        env={k:v for k,v in os.environ.items() if k in ('PATH','HOME','USER','LOGNAME','TMPDIR','LANG','LC_ALL','LC_CTYPE','TERM')}
        env.update({'CLAUDE_MY_PRIVACY_CONFIG': str(write_config(workspace)), 'CLAUDE_CONFIG_DIR':str(config),'ANTHROPIC_API_KEY':'offline-audit-placeholder','DISABLE_TELEMETRY':'1','DISABLE_ERROR_REPORTING':'1','CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC':'1'})
        # Baseline places the synthetic model first to isolate actual tools:
        # a strict undefined scan can otherwise stop the model before tools run.
        settings={'prependPlugins':['offline-tool-audit@inline' if args.baseline else 'my-privacy@inline']}
        if args.deny_bash: settings['permissions']={'deny':['Bash']}
        permission_flags=[] if args.deny_bash else ['--dangerously-skip-permissions']
        command=['/usr/bin/sandbox-exec','-p','(version 1)(allow default)(deny network*)',shutil.which('claude'),'--setting-sources','','--strict-mcp-config','--mcp-config','{"mcpServers":{}}','--settings',json.dumps(settings),*permission_flags,'--tools','Read,Bash,Grep','--plugin-dir',str(plugin),'--plugin-dir',str(mock),'-p','Perform the offline synthetic tool regression.']
        try:
            run=subprocess.run(command,cwd=workspace,env=env,capture_output=True,text=True,timeout=55,check=False)
            report['processSucceeded']=run.returncode==0
            if (workspace/'audit.json').exists():
                audit=json.loads((workspace/'audit.json').read_text());report['completed']=audit.get('complete',False);report['captures']=audit.get('captures',[])
            if (workspace/'diagnostics.json').exists():report['diagnostics']=json.loads((workspace/'diagnostics.json').read_text())
            report['mockCompleted']='OFFLINE_TOOL_AUDIT_COMPLETE' in run.stdout
            report['moduleLoadError']='Failed to load' in run.stderr or 'Failed to load' in run.stdout
            actual_text=(fixture/'config.js').read_text()
            report['fixtureChecks']={
                'localEditApplied':'after.example.invalid' in actual_text and 'before.example.invalid' not in actual_text,
                'requestedEntryRemoved':'bwg2' not in actual_text,
                'shortAliasLiteralUnchanged':'const shortAlias = "rc";' in actual_text,
                'companyAliasLiteralUnchanged':'const companyAlias = "Harborwave";' in actual_text,
                'scriptAliasLiteralUnchanged':'const scriptedAlias = "rc Harborwave";' in actual_text,
                'sourceCompanyUnchanged':'const sourceCompany = "Cedarbyte";' in actual_text,
                'fixtureUnchanged':actual_text==fixture_text,
            }
            if args.diagnose:
                combined=run.stdout+run.stderr
                report['outputFlags']={term:term.lower() in combined.lower() for term in ['Local privacy guard stopped','Privacy filtering requires','untrusted','authentication','plugin','error','audit','cannot','permission','invalid','static','typescript','approval','native','account']}
                report['outputLength']=len(combined)
        except subprocess.TimeoutExpired:
            report['timedOut']=True
    captures=report.get('captures',[])
    if args.baseline:
        report['baselineOldUndefinedHandling']=True
        report['checks']={
            'bashRejectedWithInvalidJson':any(row.get('tool')=='Bash' and row.get('phase') in ('arguments','rewrite','result') and row.get('code')=='INVALID_JSON' for row in report.get('diagnostics',[])),
            'bashDenied':bool(captures) and captures[0].get('withheld') is True,
        }
    elif args.deny_bash:
        report['nativeBashDenyConfigured']=True
        report['permissionBypassUsed']=False
        report['checks']={
            'allSixToolResultsObserved':len(captures)==6 and all(row.get('resultExists') for row in captures),
            'everyBashCallBlockedByHost':len(captures)==6 and all(captures[index].get('isError') and (captures[index].get('permissionDenied') or captures[index].get('toolUnavailable')) and not captures[index].get('withheld') for index in (0,2,4,5)),
            'blockedEditDidNotChangeFixture':report.get('fixtureChecks',{}).get('fixtureUnchanged',False),
            'modelToolResultsContainNoOriginals':bool(captures) and all(not row.get('rawVisible') for row in captures),
        }
    elif args.prefix_policy_baseline:
        report['baselineOldShellPolicy']=True
        report['checks']={
            'allSixToolResultsObserved':len(captures)==6 and all(row.get('resultExists') for row in captures),
            'sedRejectedByOldCommandList':len(captures)>4 and captures[4].get('isError') and captures[4].get('unsupportedAliasCommand'),
            'heredocRejectedByOldParser':len(captures)>5 and captures[5].get('isError') and captures[5].get('complexAliasCommand'),
            'blockedEditDidNotChangeFixture':report.get('fixtureChecks',{}).get('fixtureUnchanged',False),
            'modelToolResultsContainNoOriginals':bool(captures) and all(not row.get('rawVisible') for row in captures),
        }
    else:
        report['checks']={
            'allSixToolResultsObserved':len(captures)==6 and all(row.get('resultExists') for row in captures),
            'simpleBashListWorks':len(captures)>0 and not captures[0].get('isError') and captures[0].get('listing') and captures[0].get('hasNameAlias'),
            'grepWorksAndRedacts':len(captures)>1 and not captures[1].get('isError') and captures[1].get('match') and captures[1].get('hasCompanyAlias'),
            'readOnlyAndChainWorks':len(captures)>2 and not captures[2].get('isError') and captures[2].get('match') and captures[2].get('hasCompanyAlias'),
            'missingAliasPathGetsSpecificError':len(captures)>3 and captures[3].get('isError') and captures[3].get('missingPathCode'),
            'sedAfterVerifiedCdWorks':len(captures)>4 and not captures[4].get('isError') and captures[4].get('hasSedMarker') and captures[4].get('hasShortAlias') and captures[4].get('hasCompanyAlias'),
            'heredocAfterVerifiedCdWorks':len(captures)>5 and not captures[5].get('isError') and not captures[5].get('withheld') and captures[5].get('match') and captures[5].get('listing'),
            'localEditApplied':report.get('fixtureChecks',{}).get('localEditApplied',False),
            'requestedEntryRemoved':report.get('fixtureChecks',{}).get('requestedEntryRemoved',False),
            'shellCodeAliasesNeverRestored':all(report.get('fixtureChecks',{}).get(key,False) for key in ('shortAliasLiteralUnchanged','companyAliasLiteralUnchanged','scriptAliasLiteralUnchanged','sourceCompanyUnchanged')),
            'modelToolResultsContainNoOriginals':bool(captures) and all(not row.get('rawVisible') for row in captures),
        }
    report['passed']=report['completed'] and report.get('processSucceeded',False) and all(report['checks'].values())
    filename='tools-baseline-summary.json' if args.baseline else 'tools-prefix-baseline-summary.json' if args.prefix_policy_baseline else 'tools-permission-summary.json' if args.deny_bash else 'tools-latest-summary.json'
    (ROOT/'evidence'/filename).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return 0 if report['passed'] else 1


if __name__=='__main__':sys.exit(main())
