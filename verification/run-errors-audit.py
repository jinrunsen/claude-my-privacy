#!/usr/bin/env python3
"""Verify native errors and privacy audit persistence without a model or network.

Every command and file in this test is synthetic. The historical adapter is
restored only in a temporary plugin copy, never in the installed plugin.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from synthetic_config import write_config

ROOT = Path(__file__).resolve().parent
PRODUCTION = ROOT.parent / 'plugins/my-privacy'
AUDIT_PREFIX = 'privacy.audit.v1.'
SECRET_MARKER = 'AUDIT_ONLY_SECRET_7c9335'

OLD_RESULT_HANDLER = '''export function rewriteToolResult(answer, redact) {
  if (answer.deny !== undefined) return { deny: redact(answer.deny) };
  if (containsMedia(answer.result)) return { deny: 'Non-text tool output was withheld because this privacy mod does not inspect image, PDF, or audio contents.' };
  if (answer.isError === true) {
    const value = typeof answer.text === 'string' ? answer.text
      : answer.result === undefined ? 'The tool failed without an error message.' : answer.result;
    const error = { result: redact(value), isError: true };
    if (answer.context) error.context = redact(answer.context);
    return error;
  }
  const result = { result: redact(answer.result) };
  if (answer.isError !== undefined) result.isError = answer.isError;
  if (answer.context) result.context = redact(answer.context);
  return result;
}

'''

MOCK = r'''
import { CALLS, REPORT } from './paths.js';
const captures = [];
function result(e, answer, tools = [], stop = 'end_turn') {
  return { turnId: e.turnId, index: e.index, answer, toolUses: tools, stopReason: stop, usage: null };
}
export function register(on) {
  on('turn.step', async function* ($, e) {
    const messages = await $.session.messages({ as: 'api' });
    const tools = messages.flatMap(m => Array.isArray(m.content)
      ? m.content.filter(b => b.type === 'tool_result') : []);
    const last = tools[tools.length - 1];
    const text = last ? JSON.stringify(last.content) : '';
    if (e.index > 0) captures.push({
      resultExists: !!last,
      isError: last?.is_error === true,
      schemaMismatch: text.includes('does not match its output shape'),
      shellErrorExplained: text.includes('OFFLINE_NATIVE_FAILURE'),
      pythonErrorExplained: text.includes('RuntimeError'),
      missingFileExplained: /does not exist|No such file|not found|not exist/i.test(text),
      successVisible: text.includes('OFFLINE_SUCCESS'),
      policyCodeVisible: text.includes('COMPLEX_ALIAS_COMMAND'),
      piiTokenVisible: text.includes('<PII_EMAIL_'),
      aliasesVisible: text.includes('ryanchen') && text.includes('Harborwave'),
      originalAbsent: !/chenxinghe|Cedarbyte|synthetic.person@example.test/.test(text),
    });
    const call = CALLS[e.index];
    if (!call) {
      // A plugin-owned call exercises generated raw arguments without adding
      // deliberately tainted tool_use arguments to the model conversation.
      const blocked = await $.tool.call({ tool: 'Bash',
        command: 'printf "%s\\n" cxh > protected-args-ran.txt',
        description: 'Verify a synthetic protected argument is refused' });
      await $.fs.write(REPORT, JSON.stringify({
        complete: true,
        captures,
        protectedArgumentsDenied: typeof blocked.deny === 'string',
      }));
      yield { kind: 'text', index: 0, text: 'OFFLINE_ERRORS_AUDIT_COMPLETE' };
      yield { kind: 'stop', stopReason: 'end_turn', usage: null };
      return result(e, 'OFFLINE_ERRORS_AUDIT_COMPLETE');
    }
    yield { kind: 'tool', index: 0, id: `toolu_error_audit_${e.index}`, name: call.name };
    yield { kind: 'input', index: 0, json: JSON.stringify(call.input) };
    yield { kind: 'stop', stopReason: 'tool_use', usage: null };
    return result(e, '', [call], 'tool_use');
  });
}
'''


def audit_entries(config):
    entries = []

    def visit(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key.startswith(AUDIT_PREFIX):
                    entries.append(child)
                else:
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    for path in config.rglob('*.json'):
        try:
            visit(json.loads(path.read_text()))
        except (OSError, UnicodeError, ValueError):
            continue
    return entries


def run_case(base, cli, baseline=False):
    workspace = base / ('baseline' if baseline else 'current')
    workspace.mkdir()
    project = workspace / 'chenxinghe' / 'project'
    project.mkdir(parents=True)
    alias = str(project).replace('/chenxinghe/', '/ryanchen/')
    (project / 'synthetic-error.txt').write_text(
        'OFFLINE_NATIVE_FAILURE chenxinghe Cedarbyte synthetic.person@example.test\n')
    config = workspace / 'config'
    config.mkdir(mode=0o700)
    plugin = workspace / 'my-privacy'
    shutil.copytree(PRODUCTION, plugin)
    if baseline:
        content = plugin / 'lib/content.js'
        text = content.read_text()
        start = text.index('export function rewriteToolResult(')
        end = text.index('export function compactMessages(', start)
        content.write_text(text[:start] + OLD_RESULT_HANDLER + text[end:])
    mock = workspace / 'mock'
    (mock / '.claude-plugin').mkdir(parents=True)
    (mock / 'hooks').mkdir()
    (mock / '.claude-plugin/plugin.json').write_text(json.dumps({
        'name': 'offline-error-audit', 'version': '0.1.0',
        'description': 'Synthetic native error regression without network',
    }))
    (mock / 'hooks/hooks.json').write_text('{"modules":["./register.js"]}')
    (mock / 'hooks/register.js').write_text(MOCK)
    calls = [
        {'name': 'Bash', 'input': {
            'command': f'cd {alias} && {SECRET_MARKER}=synthetic printf "%s\\n" "$(cat synthetic-error.txt)"; exit 7',
            'description': 'Produce a synthetic native shell error',
        }},
        {'name': 'Bash', 'input': {
            'command': f'cd {alias} && python3 -c "from pathlib import Path; raise RuntimeError(Path(\'synthetic-error.txt\').read_text())"',
            'description': 'Produce a synthetic Python traceback',
        }},
        {'name': 'Read', 'input': {'file_path': str(workspace / 'native-missing.txt')}},
        {'name': 'Bash', 'input': {
            'command': f'cd {alias} && {SECRET_MARKER}=synthetic printf "%s\\n" OFFLINE_SUCCESS && cat synthetic-error.txt',
            'description': 'Verify successful output still has its native shape',
        }},
        {'name': 'Bash', 'input': {
            'command': f'cd {alias} || printf forbidden > complex-command-ran.txt',
            'description': 'Verify a synthetic ambiguous directory prefix is refused',
        }},
    ]
    (mock / 'hooks/paths.js').write_text(
        'export const CALLS = ' + json.dumps(calls) + ';\n'
        'export const REPORT = ' + json.dumps(str(workspace / 'results.json')) + ';\n')
    env = {key: value for key, value in os.environ.items() if key in (
        'PATH', 'HOME', 'USER', 'LOGNAME', 'TMPDIR', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TERM')}
    env.update({
        'CLAUDE_MY_PRIVACY_CONFIG': str(write_config(workspace)), 'CLAUDE_CONFIG_DIR': str(config), 'ANTHROPIC_API_KEY': 'offline-audit-placeholder',
        'DISABLE_TELEMETRY': '1', 'DISABLE_ERROR_REPORTING': '1',
        'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1',
    })
    common = ['/usr/bin/sandbox-exec', '-p', '(version 1)(allow default)(deny network*)', cli,
        '--setting-sources', '', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
        '--settings', '{"prependPlugins":["my-privacy@inline"]}',
        '--dangerously-skip-permissions', '--tools', 'Read,Bash', '--plugin-dir', str(plugin)]
    run = subprocess.run(common + ['--plugin-dir', str(mock), '-p',
        'Perform the offline synthetic native-error regression.'], cwd=workspace,
        env=env, capture_output=True, text=True, timeout=55, check=False)
    case = {'processSucceeded': run.returncode == 0,
        'mockCompleted': 'OFFLINE_ERRORS_AUDIT_COMPLETE' in run.stdout,
        'moduleLoadError': 'Failed to load' in run.stdout + run.stderr}
    result_path = workspace / 'results.json'
    if result_path.is_file():
        case.update(json.loads(result_path.read_text()))
    case['blockedCommandsDidNotRun'] = not any(
        path.is_file() for path in workspace.rglob('*-ran.txt'))
    if not baseline:
        before = audit_entries(config)
        command = subprocess.run(common + ['-p', '/my-privacy-audit'], cwd=workspace,
            env=env, capture_output=True, text=True, timeout=55, check=False)
        after = audit_entries(config)
        serialized = json.dumps(after, ensure_ascii=False)
        field_set = {'schema', 'version', 'time', 'kind', 'stage', 'code', 'tool', 'execution', 'input', 'output'}
        input_fields = {'type', 'commandLength', 'leadingCd', 'multiline', 'heredoc', 'shellVariable'}
        output_fields = {'type', 'resultType', 'isError', 'hasDenial'}
        case['audit'] = {
            'storedEventCount': len(after),
            'storedEventsExist': bool(after),
            'eventsPersistedAcrossProcess': bool(before) and before == after,
            'boundedEventCount': 0 < len(after) <= 300,
            'summaryCommandSucceeded': command.returncode == 0,
            'summaryReportsPersistedCount': f'audit: {len(after)} retained events (limit 300).' in command.stdout,
            'summarySeparatesNativeErrorsAndPrivacyBlocks': 'tool_error=3' in command.stdout and 'privacy_block=2' in command.stdout,
            'summaryContainsExpectedCodes': all(code in command.stdout for code in
                ('TOOL_ERROR=3', 'COMPLEX_ALIAS_COMMAND=1', 'RAW_PRIVATE_ARGUMENTS=1')),
            'summaryProvidesAnalysis': 'Analysis:' in command.stdout and 'Native tool failures' in command.stdout,
            'storedEventsHaveStrictMetadataShape': bool(after) and all(
                isinstance(row, dict) and set(row) == field_set
                and isinstance(row.get('input'), dict) and set(row['input']) == input_fields
                and isinstance(row.get('output'), dict) and set(row['output']) == output_fields
                for row in after),
            'summaryContainsNoRawPrivateValues': not any(value in command.stdout for value in
                ('chenxinghe', 'Cedarbyte', 'synthetic.person@example.test', SECRET_MARKER)),
            'storedMetadataContainsNoPrivateValues': not any(value in serialized for value in
                ('chenxinghe', 'Cedarbyte', 'synthetic.person@example.test', SECRET_MARKER)),
            'storedMetadataContainsNoCommandsOrFixturePaths': not any(value in serialized for value in
                ('printf', 'python3', 'synthetic-error.txt', 'native-missing.txt', str(workspace))),
        }
    return case


def main():
    os.umask(0o077)
    cli = shutil.which('claude')
    report = {'networkDenied': True, 'syntheticFixturesOnly': True,
        'isolatedConfiguration': True, 'passed': False}
    if sys.platform != 'darwin' or cli is None or not Path('/usr/bin/sandbox-exec').is_file():
        report['prerequisitesMissing'] = True
    else:
        try:
            with tempfile.TemporaryDirectory(prefix='my-privacy-error-e2e-') as directory:
                workspace = Path(directory)
                report['baseline'] = run_case(workspace, cli, baseline=True)
                report['current'] = run_case(workspace, cli)
        except subprocess.TimeoutExpired:
            report['timedOut'] = True
    old = report.get('baseline', {})
    current = report.get('current', {})
    old_rows = old.get('captures', [])
    rows = current.get('captures', [])
    report['checks'] = {
        'baselineReproducesNativeBashSchemaError': len(old_rows) == 5 and old_rows[0].get('schemaMismatch', False),
        'bothMockRunsCompleted': old.get('mockCompleted', False) and current.get('mockCompleted', False),
        'allFiveNativeResultsObserved': len(rows) == 5 and all(row.get('resultExists') for row in rows),
        'nativeErrorsRemainErrors': len(rows) == 5 and all(rows[index].get('isError') for index in (0, 1, 2)),
        'shellErrorExplanationSurvives': len(rows) == 5 and rows[0].get('shellErrorExplained', False),
        'pythonErrorExplanationSurvives': len(rows) == 5 and rows[1].get('pythonErrorExplained', False),
        'missingReadExplanationSurvives': len(rows) == 5 and rows[2].get('missingFileExplained', False),
        'nativeErrorTextIsRedacted': len(rows) == 5 and all(rows[index].get('piiTokenVisible') and rows[index].get('aliasesVisible') for index in (0, 1)),
        'successfulBashStillWorks': len(rows) == 5 and not rows[3].get('isError') and rows[3].get('successVisible', False),
        'complexAliasPolicyStillBlocks': len(rows) == 5 and rows[4].get('isError', False) and rows[4].get('policyCodeVisible', False),
        'rawProtectedArgumentsStillBlock': current.get('protectedArgumentsDenied', False),
        'blockedCommandsDidNotRun': current.get('blockedCommandsDidNotRun', False),
        'noNativeOutputSchemaErrors': bool(rows) and all(not row.get('schemaMismatch') for row in rows),
        'allModelToolResultsAreSanitized': bool(rows) and all(row.get('originalAbsent') for row in rows),
        'auditPersistenceAndPrivacyPass': bool(current.get('audit')) and all(value for key, value in current.get('audit', {}).items() if key != 'storedEventCount'),
    }
    report['passed'] = bool(current.get('processSucceeded')) and all(report['checks'].values())
    (ROOT / 'evidence' / 'errors-audit-latest-summary.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
