#!/usr/bin/env python3
"""Exercise same-process privacy recovery with a fake model and no network."""

import json
import os
from pathlib import Path
import fcntl
import pty
import re
import struct
import termios
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
import { ALIAS_COMMAND, PRIVATE_COMMAND, REPORT, INITIAL, SENTINEL, INVOCATION, SESSION } from './paths.js';
let emitted = 0;
let nativeCalls = 0;
let nativeCommandUnchanged = false;
function result(e, answer, tools = [], stop = 'end_turn') {
  return { turnId:e.turnId, index:e.index, answer, toolUses:tools, stopReason:stop, usage:null };
}
export function register(on) {
  on('tool.call', async ($, e, next) => {
    nativeCalls += 1;
    nativeCommandUnchanged = e.command === ALIAS_COMMAND;
    return next(e);
  });
  // Privacy recovery must answer before this hook (and core's summarizer).
  on('session.compact', async ($) => {
    await $.fs.write(SENTINEL, 'DOWNSTREAM_COMPACTION_REACHED');
    return { skip: 'The offline harness refuses downstream summarization.' };
  });
  on('turn.complete', async ($, e, next) => {
    if (emitted === 2 && !await $.fs.exists(INITIAL)) {
      await $.fs.write(SESSION, await $.session.id());
      const messages = await $.session.messages({as:'api'});
      const text = JSON.stringify(messages);
      await $.fs.write(INITIAL, JSON.stringify({
        guardBlockedFollowup: e.answer.includes('Local privacy guard stopped'),
        rawToolArgumentWasInHistory: text.includes('other.synthetic@example.test'),
        rejectedCallHasResult: text.includes('toolu_recovery_1') && /unmasked value|private original values/.test(text),
        nativeCalls,
        nativeCommandUnchanged,
      }));
      // stream-json user messages are model prompts, not interactive slash
      // commands. Invoke the actual registered command after this turn's
      // completion hook has returned; command.run forbids a waiting-turn hook.
      $.clock.after(150, async () => {
        try {
          const available = await $.command.list();
          const target = available.find(c => c.name === 'my-privacy-recover')
            ?? available.find(c => c.name.endsWith(':my-privacy-recover'));
          const answer = await $.command.run({command:target?.name ?? 'my-privacy-recover'});
          await $.fs.write(INVOCATION, JSON.stringify({resolved:true,
            targetFound: !!target,
            hasText: typeof answer.text === 'string',
            commandUnavailable: /unavailable|not available|not supported|headless|non.interactive|print mode/i.test(answer.text ?? ''),
            recoveryFailed: /could not|cannot|failed/i.test(answer.text ?? ''),
            completed: typeof answer.text === 'string' && answer.text.includes('recovery completed')}));
        } catch {
          await $.fs.write(INVOCATION, JSON.stringify({resolved:false,completed:false}));
        }
      });
    }
    return next(e);
  });
  on('turn.step', async function* ($, e) {
    if (emitted < 2) {
      const call = {name:'Bash', input:{command:emitted === 0 ? ALIAS_COMMAND : PRIVATE_COMMAND,
        description:'Synthetic MyPrivacy recovery regression'}};
      const index = emitted++;
      yield {kind:'tool', index:0, id:`toolu_recovery_${index}`, name:'Bash'};
      yield {kind:'input', index:0, json:JSON.stringify(call.input)};
      yield {kind:'stop', stopReason:'tool_use', usage:null};
      return result(e, '', [call], 'tool_use');
    }
    const messages = await $.session.messages({as:'api'});
    const text = JSON.stringify(messages);
    await $.fs.write(REPORT, JSON.stringify({
      safeFollowupReachedModelHook: true,
      protectedToolArgumentsRemoved: !text.includes('other.synthetic@example.test'),
      emailTokenPresent: text.includes('<PII_EMAIL_'),
      safeAliasEmailPreserved: text.includes('ryanchen@harborwave.com'),
      rejectedToolIdentityPreserved: text.includes('toolu_recovery_1'),
      noOpaqueMediaOrThinking: !messages.some(m => Array.isArray(m.content) && m.content.some(b => ['thinking','redacted_thinking','image','document','audio'].includes(b.type))),
      nativeCalls,
      nativeCommandUnchanged,
    }));
    yield {kind:'text', index:0, text:'OFFLINE_RECOVERY_FOLLOWUP_COMPLETE'};
    yield {kind:'stop', stopReason:'end_turn', usage:null};
    return result(e, 'OFFLINE_RECOVERY_FOLLOWUP_COMPLETE');
  });
}
'''

OBSERVER = r'''
import { COMPACT, COMMAND } from './paths.js';
export function register(on) {
  on('session.compact', async ($, e, next) => {
    const answer = await next(e);
    const text = JSON.stringify(answer.messages ?? []);
    await $.fs.write(COMPACT, JSON.stringify({
      triggerWasPlugin: e.trigger === 'plugin',
      inputHadHostHandles: e.messages.some(m => typeof m.handle === 'string'),
      returnedMessages: Array.isArray(answer.messages),
      outputRemovedHostHandles: Array.isArray(answer.messages) && answer.messages.every(m => !Object.hasOwn(m,'handle')),
      privateArgumentRemoved: !text.includes('other.synthetic@example.test'),
      tokenPresent: text.includes('<PII_EMAIL_'),
      toolIdentityPreserved: text.includes('toolu_recovery_1'),
      skipped: typeof answer.skip === 'string',
    }));
    return answer;
  });
  on('command.run', {command:'my-privacy-recover'}, async ($, e, next) => {
    const answer = await next(e);
    await $.fs.write(COMMAND, JSON.stringify({
      answered: typeof answer.text === 'string',
      noPrivateValues: !/other.synthetic@example.test|chenxinghe|cedarbyte/i.test(answer.text ?? ''),
      reportsRecovery: /recover|rebuild|rebuilt|saniti|reconstruct/i.test(answer.text ?? ''),
      reportsResumeRestriction: /resum|new session/i.test(answer.text ?? ''),
    }));
    return answer;
  });
}
'''


def create_plugin(path, name, source, values):
    (path / '.claude-plugin').mkdir(parents=True)
    (path / 'hooks').mkdir()
    (path / '.claude-plugin/plugin.json').write_text(json.dumps({
        'name': name, 'version': '0.1.0', 'description': 'Offline synthetic recovery verification',
    }))
    (path / 'hooks/hooks.json').write_text('{"modules":["./register.js"]}')
    (path / 'hooks/register.js').write_text(source)
    (path / 'hooks/paths.js').write_text(''.join(
        'export const ' + name + '=' + json.dumps(value) + ';\n' for name, value in values.items()))


def read_json(path):
    return json.loads(path.read_text()) if path.is_file() else {}


def recovery_outcome(config):
    def contains(value):
        if isinstance(value,dict):
            for key,child in value.items():
                if key.startswith('privacy.audit.v1.') and isinstance(child,dict) and child.get('code') in ('RECOVERY_SUCCEEDED','RECOVERY_FAILED'):
                    return child['code']
                found = contains(child)
                if found: return found
        elif isinstance(value,list):
            for child in value:
                found = contains(child)
                if found: return found
        return None
    for path in (config / 'plugins/store').glob('*.json'):
        try:
            found = contains(json.loads(path.read_text()))
            if found: return found
        except (OSError,ValueError): pass
    return None


def drive_interactive(command, workspace, config, env, report):
    master, slave = pty.openpty()
    fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',48,150,0,0))
    output = []
    process = subprocess.Popen(command + ['OFFLINE_RECOVERY_INITIAL: Run the synthetic alias and rejection checks.'],
        cwd=workspace,env={**env,'TERM':'xterm-256color'},stdin=slave,stdout=slave,stderr=slave,
        close_fds=True,start_new_session=True)
    os.close(slave)

    def read_terminal():
        while True:
            try: chunk = os.read(master,65536)
            except OSError: break
            if not chunk: break
            output.append(chunk.decode('utf-8','replace'))
            if b'\x1b[6n' in chunk:
                try: os.write(master,b'\x1b[1;1R')
                except OSError: break

    reader = threading.Thread(target=read_terminal,daemon=True)
    reader.start()
    accepted_trust = False

    def wait_for(predicate,limit=45):
        nonlocal accepted_trust
        deadline = time.monotonic()+limit
        while time.monotonic()<deadline:
            if predicate(): return True
            if process.poll() is not None: return False
            visible = re.sub(r'\s+','',re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','', ''.join(output)[-16000:]))
            if not accepted_trust and 'Yes,Itrustthisfolder' in visible and 'No,exit' in visible:
                os.write(master,b'\x1b[B')
                time.sleep(0.1)
                os.write(master,b'\r')
                accepted_trust = True
                report['syntheticWorkspaceTrustAccepted'] = True
            time.sleep(0.1)
        return False

    try:
        report['initialResultReceived'] = wait_for(lambda:(workspace/'initial.json').is_file())
        if report['initialResultReceived']:
            report['recoveryCommandObserved'] = wait_for(lambda:(workspace/'invocation.json').is_file())
            if report['recoveryCommandObserved']:
                wait_for(lambda:recovery_outcome(config) is not None)
                report['recoveryVerified'] = recovery_outcome(config) == 'RECOVERY_SUCCEEDED'
            if report.get('recoveryVerified'):
                os.write(master,b'OFFLINE_RECOVERY_FOLLOWUP: Confirm sanitized history can continue.\r')
                report['followupObserved'] = wait_for(lambda:(workspace/'followup.json').is_file())
        if process.poll() is None:
            os.write(master,b'\x04')
            time.sleep(0.2)
            if process.poll() is None: os.write(master,b'\x04')
            process.wait(timeout=10)
    except (OSError,subprocess.TimeoutExpired):
        report['terminalStoppedAfterChecks'] = True
    finally:
        if process.poll() is None:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill();process.wait(timeout=5)
        reader.join(timeout=2)
        os.close(master)
    report['processSucceeded'] = process.returncode == 0 or bool(report.get('followupObserved'))
    report['moduleLoadError'] = 'Failed to load' in ''.join(output)
    if '--diagnose' in sys.argv and not report.get('followupObserved'):
        text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','', ''.join(output))
        print('Synthetic terminal diagnostic:',text[-5000:].replace(str(workspace),'<SYNTHETIC_WORKSPACE>'))
    return output


def main():
    os.umask(0o077)
    report = {'networkDenied': True, 'syntheticFixturesOnly': True, 'sameProcessRecovery': True, 'passed': False}
    cli = shutil.which('claude')
    if sys.platform != 'darwin' or not cli or not Path('/usr/bin/sandbox-exec').is_file():
        report['prerequisitesMissing'] = True
    else:
        with tempfile.TemporaryDirectory(prefix='my-privacy-recovery-e2e-') as directory:
            workspace = Path(directory)
            project = workspace / 'chenxinghe' / 'project'
            project.mkdir(parents=True)
            (workspace / 'ryanchen').symlink_to(workspace / 'chenxinghe', target_is_directory=True)
            alias = workspace / 'ryanchen' / 'project'
            alias_command = f'cd {alias} && printf "%s\\n" ryanchen@harborwave.com > alias-email.txt'
            private_command = 'printf "%s\\n" other.synthetic@example.test > blocked-command-ran.txt'
            config = workspace / 'config'
            config.mkdir(mode=0o700)
            (config / '.claude.json').write_text(json.dumps({
                'hasCompletedOnboarding':True,'theme':'dark','autoUpdates':False,
                'bypassPermissionsModeAccepted':True,
                'customApiKeyResponses':{'approved':['offline-audit-placeholder'[-20:]],'rejected':[]},
                'projects':{value:{'hasTrustDialogAccepted':True,'hasCompletedProjectOnboarding':True}
                    for value in (str(workspace),str(workspace.resolve()))},
            }))
            plugin = workspace / 'my-privacy'
            shutil.copytree(PRODUCTION, plugin)
            if '--probe-command-compact' in sys.argv:
                hook = plugin/'hooks/register.js'
                source = hook.read_text()
                marker = 'const outcome = await $.session.compact();'
                if source.count(marker) != 1: raise RuntimeError('Compact probe marker changed')
                source = source.replace(marker, "const outcome = await $.command.run({command:'compact'});")
                source = source.replace("recovering && event.trigger === 'plugin'", "recovering && (event.trigger === 'plugin' || event.trigger === 'manual')")
                hook.write_text(source)
                report['temporaryCommandCompactProbe'] = True
            if '--diagnose' in sys.argv:
                hook = plugin/'hooks/register.js'
                source = hook.read_text()
                marker = "  on('session.compact', async ($, event, next) => {"
                if source.count(marker) != 1: raise RuntimeError('Compact diagnostic marker changed')
                source = 'const COMPACT_DIAGNOSTIC=' + json.dumps(str(workspace/'compact-diagnostic.json')) + ';\n' + source
                source = source.replace(marker, marker+"\n    await $.fs.write(COMPACT_DIAGNOSTIC, JSON.stringify({ recovering, triggerPlugin: event.trigger === 'plugin', hasAgent: !!event.agentId }));")
                hook.write_text(source)
            model = workspace / 'model'
            observer = workspace / 'observer'
            create_plugin(model, 'offline-recovery-model', MODEL, {
                'ALIAS_COMMAND': alias_command, 'PRIVATE_COMMAND': private_command,
                'REPORT': str(workspace / 'followup.json'), 'INITIAL': str(workspace / 'initial.json'),
                'SENTINEL': str(workspace / 'summarizer-ran.txt'),
                'INVOCATION': str(workspace / 'invocation.json'),
                'SESSION': str(workspace / 'session-id.txt'),
            })
            create_plugin(observer, 'offline-recovery-observer', OBSERVER, {
                'COMPACT': str(workspace / 'compact.json'), 'COMMAND': str(workspace / 'command.json'),
            })
            env = {key:value for key,value in os.environ.items() if key in (
                'PATH','HOME','USER','LOGNAME','TMPDIR','LANG','LC_ALL','LC_CTYPE','TERM')}
            env.update({'CLAUDE_MY_PRIVACY_CONFIG': str(write_config(workspace)), 'CLAUDE_CONFIG_DIR':str(config), 'ANTHROPIC_API_KEY':'offline-audit-placeholder',
                'DISABLE_TELEMETRY':'1', 'DISABLE_ERROR_REPORTING':'1', 'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC':'1'})
            command = ['/usr/bin/sandbox-exec','-p','(version 1)(allow default)(deny network*)',cli,
                '--setting-sources','','--strict-mcp-config','--mcp-config','{"mcpServers":{}}',
                '--settings','{"prependPlugins":["offline-recovery-observer@inline","my-privacy@inline"]}',
                '--dangerously-skip-permissions','--tools','Bash','--plugin-dir',str(observer),
                '--plugin-dir',str(plugin),'--plugin-dir',str(model)]
            output = drive_interactive(command,workspace,config,env,report)
            report['initial'] = read_json(workspace / 'initial.json')
            report['recovery'] = read_json(workspace / 'command.json')
            report['invocation'] = read_json(workspace / 'invocation.json')
            report['compaction'] = read_json(workspace / 'compact.json')
            report['followup'] = read_json(workspace / 'followup.json')
            if '--diagnose' in sys.argv:
                report['compactDiagnostic'] = read_json(workspace / 'compact-diagnostic.json')
            report['aliasFileCorrect'] = (project / 'alias-email.txt').is_file() and (project / 'alias-email.txt').read_text() == 'ryanchen@harborwave.com\n'
            report['rejectedCommandNeverRan'] = not (workspace / 'blocked-command-ran.txt').exists() and not (project / 'blocked-command-ran.txt').exists()
            report['downstreamSummarizerNeverRan'] = not (workspace / 'summarizer-ran.txt').exists()
            if report.get('followupObserved'):
                session_id = (workspace / 'session-id.txt').read_text() if (workspace / 'session-id.txt').is_file() else None
                if session_id:
                    previous_compact = read_json(workspace / 'compact.json')
                    resumed = subprocess.run(command + ['--resume',session_id,'-p','/my-privacy-recover'],
                        cwd=workspace,env=env,capture_output=True,text=True,timeout=40,check=False)
                    report['resume'] = {
                        'commandHandled': resumed.returncode in (0,1),
                        'restrictionExplained': 'cannot repair a resumed session' in resumed.stdout,
                        'noNewCompaction': previous_compact == read_json(workspace / 'compact.json'),
                        'didNotReachModel': 'OFFLINE_RECOVERY_FOLLOWUP_COMPLETE' not in resumed.stdout,
                    }
    initial = report.get('initial', {})
    compact = report.get('compaction', {})
    followup = report.get('followup', {})
    report['checks'] = {
        'aliasEmailAllowedUnchanged': report.get('aliasFileCorrect',False) and initial.get('nativeCommandUnchanged',False),
        'rawEmailCallDeniedThenHistoryGuardStopped': initial.get('rejectedCallHasResult',False) and initial.get('guardBlockedFollowup',False),
        'rawRejectedArgumentPresentBeforeRecovery': initial.get('rawToolArgumentWasInHistory',False),
        'recoveryRunsLocallyWithoutSummarizer': report.get('recoveryVerified',False) and report.get('downstreamSummarizerNeverRan',False),
        'recoveryCompactsDirectly': compact.get('triggerWasPlugin',False) and compact.get('returnedMessages',False) and not compact.get('skipped',True),
        'hostReplayHandlesRemoved': compact.get('inputHadHostHandles',False) and compact.get('outputRemovedHostHandles',False),
        'recoveryRewritesToolInputsWithToken': compact.get('privateArgumentRemoved',False) and compact.get('tokenPresent',False),
        'toolIdentityPreserved': compact.get('toolIdentityPreserved',False) and followup.get('rejectedToolIdentityPreserved',False),
        'safeFollowupPassesHistoryGuard': report.get('followupObserved',False) and followup.get('safeFollowupReachedModelHook',False),
        'followupHistoryHasNoRawEmail': followup.get('protectedToolArgumentsRemoved',False),
        'safeEmailAliasSurvivesRecovery': followup.get('safeAliasEmailPreserved',False),
        'noRejectedToolWasExecutedOrReplayed': report.get('rejectedCommandNeverRan',False) and followup.get('nativeCalls') == 1,
        'resumedSessionRestrictionRemains': bool(report.get('resume')) and all(report.get('resume',{}).values()),
    }
    report['passed'] = bool(report.get('processSucceeded')) and all(report['checks'].values())
    (ROOT / 'evidence' / 'recovery-latest-summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
