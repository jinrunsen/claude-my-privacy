#!/usr/bin/env python3
"""Check the real terminal render boundary with fictional, offline model replies."""

import fcntl
import json
import os
from pathlib import Path
import re
import select
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time

from synthetic_config import write_config


ROOT = Path(__file__).resolve().parent
PRODUCTION = ROOT.parent / 'plugins/my-privacy'
ALIASED = '陈瑞恩 RyanChen 海岚数科 Harborwave ryanchen@harborwave.example'
PROMPT = 'OFFLINE_DISPLAY_FIRST: 陈星河 ChenXingHe 云杉智科 Cedarbyte'
MODEL = r'''
import {REPORT, RENDER, ANSWER} from './paths.js';
let turns=0;
let renders=0;
let restoredReplySeen=false;
export function register(on) {
  on('ui.render',{component:'AssistantMessage'},async($,e,next)=>{
    renders++;
    restoredReplySeen=restoredReplySeen||(e.props.text.includes('OFFLINE_DISPLAY_REPLY_COMPLETE')
      &&e.props.text.includes('chenxinghe@cedarbyte.example')
      &&e.props.text.includes('陈星河')&&e.props.text.includes('云杉智科')
      &&e.props.text.includes('ChenXingHe')&&e.props.text.includes('Cedarbyte')
      &&!/ryanchen|harborwave|陈瑞恩|海岚数科/i.test(e.props.text));
    await $.fs.write(RENDER,JSON.stringify({renders,
      restoredReplySeen,
      terminal:e.surface==='terminal'}));
    return next(e);
  });
  on('turn.step',async function*($,e){
    turns++;
    const messages=await $.session.messages({as:'api'});
    const text=JSON.stringify(messages);
    const firstPrompt=JSON.stringify(messages.filter(m=>m.role==='user'
      &&JSON.stringify(m.content).includes('OFFLINE_DISPLAY_FIRST')));
    const assistant=messages.filter(m=>m.role==='assistant');
    const history=JSON.stringify(assistant);
    await $.fs.write(REPORT,JSON.stringify({turns,
      modelPromptHasAliases:/RyanChen/.test(firstPrompt)&&/Harborwave/.test(firstPrompt)
        &&firstPrompt.includes('陈瑞恩')&&firstPrompt.includes('海岚数科'),
      modelPromptHasNoOriginals:!/chenxinghe|cedarbyte|陈星河|云杉智科/i.test(text),
      priorReplyExists:assistant.length>0,
      priorReplyAliased:history.includes('ryanchen@harborwave.example'),
      priorReplyHasNoOriginals:!/chenxinghe|cedarbyte|陈星河|云杉智科/i.test(history)}));
    const answer=turns===1?ANSWER:'OFFLINE_DISPLAY_FOLLOWUP_COMPLETE';
    yield {kind:'text',index:0,text:answer};
    yield {kind:'stop',stopReason:'end_turn',usage:null};
    return {turnId:e.turnId,index:e.index,answer,toolUses:[],stopReason:'end_turn',usage:null};
  });
}
'''


def read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def prepare(workspace, cli):
    config = workspace / 'config'
    config.mkdir(mode=0o700)
    key = 'offline-display-placeholder'
    # Synthetic setup state only: no host settings or authentication are copied.
    (config / '.claude.json').write_text(json.dumps({
        'hasCompletedOnboarding': True, 'theme': 'dark',
        'lastOnboardingVersion': '2.1.290',
        'customApiKeyResponses': {'approved': [key[-20:]], 'rejected': []},
        'projects': {str(workspace.resolve()): {'hasTrustDialogAccepted': True}},
    }))
    plugin = workspace / 'my-privacy'
    shutil.copytree(PRODUCTION, plugin)
    model = workspace / 'model'
    (model / '.claude-plugin').mkdir(parents=True)
    (model / 'hooks').mkdir()
    (model / '.claude-plugin/plugin.json').write_text(json.dumps({
        'name': 'offline-display-model', 'version': '0.1.0',
        'description': 'Fictional offline assistant display verification',
    }))
    (model / 'hooks/hooks.json').write_text('{"modules":["./register.js"]}')
    (model / 'hooks/register.js').write_text(MODEL)
    values = {'REPORT': str(workspace / 'model.json'), 'RENDER': str(workspace / 'render.json'),
              'ANSWER': '**' + ALIASED + '**\n\nOFFLINE_DISPLAY_REPLY_COMPLETE'}
    (model / 'hooks/paths.js').write_text(''.join(
        'export const ' + key + '=' + json.dumps(value) + ';\n' for key, value in values.items()
    ))
    # Match the native regression harness: preserve OS account discovery while
    # CLAUDE_CONFIG_DIR and the explicit mapping override isolate plugin state.
    env = {key: value for key, value in os.environ.items()
           if key in ('PATH', 'HOME', 'USER', 'LOGNAME', 'TMPDIR', 'LANG', 'LC_ALL', 'LC_CTYPE')}
    env.update({
        'TERM': 'xterm-256color', 'CLAUDE_CONFIG_DIR': str(config),
        'CLAUDE_MY_PRIVACY_CONFIG': str(write_config(workspace)),
        'ANTHROPIC_API_KEY': key, 'DISABLE_TELEMETRY': '1',
        'DISABLE_ERROR_REPORTING': '1', 'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1',
    })
    command = ['/usr/bin/sandbox-exec', '-p', '(version 1)(allow default)(deny network*)', cli,
               '--setting-sources', '', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
               '--settings', '{"prependPlugins":["my-privacy@inline"]}',
               '--permission-mode', 'dontAsk', '--tools', '',
               '--plugin-dir', str(plugin), '--plugin-dir', str(model)]
    return command, env


def transcript_checks(workspace):
    messages = []
    for path in (workspace / 'config/projects').rglob('*.jsonl'):
        for line in path.read_text().splitlines():
            row = json.loads(line)
            if row.get('type') == 'assistant' and isinstance(row.get('message'), dict):
                messages.append(row['message'].get('content'))
    text = json.dumps(messages, ensure_ascii=False)
    return {'savedAssistantReplyExists': bool(messages),
            'savedAssistantReplyHasAliases': 'ryanchen@harborwave.example' in text,
            'savedAssistantReplyHasNoOriginals': not re.search(r'chenxinghe|cedarbyte|陈星河|云杉智科', text, re.I)}


def kill_group(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass  # The child may finish between poll() and killpg().
    process.wait(timeout=5)


def interactive(workspace, cli):
    command, env = prepare(workspace, cli)
    master, slave = os.openpty()
    try:
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 50, 160, 0, 0))
        process = subprocess.Popen(command + [PROMPT], cwd=workspace, env=env,
                                   stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
    except OSError:
        os.close(master)
        raise
    finally:
        os.close(slave)
    chunks = []
    followup_sent = False
    exit_sent = False
    deadline = time.monotonic() + 65
    trusted = False
    try:
        while time.monotonic() < deadline and process.poll() is None:
            readable, _, _ = select.select([master], [], [], 0.1)
            if readable:
                try:
                    data = os.read(master, 65536)
                except OSError:
                    break
                if not data:
                    break
                chunks.append(data)
            text = b''.join(chunks).decode('utf-8', errors='replace')
            plain = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', text)
            if not trusted and 'Yes,Itrustthisfolder' in plain.replace(' ', ''):
                # Only this newly created fictional workspace is authorized.
                os.write(master, b'\x1b[B\r')
                trusted = True
            if not followup_sent and 'OFFLINE_DISPLAY_REPLY_COMPLETE' in text:
                time.sleep(0.2)
                os.write(master, b'OFFLINE_DISPLAY_FOLLOWUP\r')
                followup_sent = True
            if followup_sent and not exit_sent and 'OFFLINE_DISPLAY_FOLLOWUP_COMPLETE' in text:
                time.sleep(0.2)
                os.write(master, b'/exit\r')
                exit_sent = True
        # PTY EOF can precede normal /exit teardown and transcript flushing.
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            kill_group(process)
    finally:
        if process.poll() is None:
            kill_group(process)
        os.close(master)
    text = b''.join(chunks).decode('utf-8', errors='replace')
    # Only fictional terminal output is inspected, and it is never published.
    model = read_json(workspace / 'model.json')
    render = read_json(workspace / 'render.json')
    return {
        'processSucceeded': process.returncode == 0,
        'firstReplyReachedTerminal': 'OFFLINE_DISPLAY_REPLY_COMPLETE' in text,
        'terminalShowsRestoredAccount': 'chenxinghe@cedarbyte.example' in text,
        'terminalShowsRestoredChinese': '陈星河' in text and '云杉智科' in text,
        'followupCompleted': 'OFFLINE_DISPLAY_FOLLOWUP_COMPLETE' in text,
        'modelUsedAliases': model.get('modelPromptHasAliases') is True and model.get('modelPromptHasNoOriginals') is True,
        'laterModelHistoryRemainsAliased': model.get('turns') == 2 and model.get('priorReplyExists') is True
            and model.get('priorReplyAliased') is True and model.get('priorReplyHasNoOriginals') is True,
        'realTerminalRenderHookObserved': render.get('renders', 0) > 0 and render.get('terminal') is True,
        'realRenderPropsRestoreOnlyTheVisibleReply': render.get('restoredReplySeen') is True,
        **transcript_checks(workspace),
    }


def printed(workspace, cli):
    command, env = prepare(workspace, cli)
    with subprocess.Popen(command + ['-p', PROMPT], cwd=workspace, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                          start_new_session=True) as child:
        try:
            stdout, _ = child.communicate(timeout=40)
        finally:
            if child.poll() is None:
                kill_group(child)
    model = read_json(workspace / 'model.json')
    return {
        'processSucceeded': child.returncode == 0,
        'printKeepsAliases': ALIASED in stdout,
        'printDoesNotRestoreOriginals': not re.search(r'chenxinghe|cedarbyte|陈星河|云杉智科', stdout, re.I),
        'modelUsedAliases': model.get('modelPromptHasAliases') is True and model.get('modelPromptHasNoOriginals') is True,
        **transcript_checks(workspace),
    }


def main():
    os.umask(0o077)
    cli = shutil.which('claude')
    report = {'scope': 'offline terminal display, model/session separation, and headless print', 'passed': False}
    if sys.platform != 'darwin' or not cli or not Path('/usr/bin/sandbox-exec').is_file():
        report['prerequisitesMissing'] = True
    else:
        try:
            with tempfile.TemporaryDirectory(prefix='my-privacy-display-e2e-') as directory:
                workspace = Path(directory)
                for name, run in [('interactive', interactive), ('print', printed)]:
                    case = workspace / name
                    case.mkdir(mode=0o700)
                    report[name] = run(case, cli)
            report['passed'] = all(all(report[name].values()) for name in ('interactive', 'print'))
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            report['failedBeforeCompleteReport'] = True
            report['failureClass'] = type(error).__name__
            report['failureStage'] = name
    (ROOT / 'evidence').mkdir(exist_ok=True)
    (ROOT / 'evidence/display-latest-summary.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
