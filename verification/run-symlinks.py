#!/usr/bin/env python3
"""Exercise native alias symlinks with real CLI tools, a fake model, and no network."""

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
SANDBOX = Path("/usr/bin/sandbox-exec")

MOCK = r'''
import { CALLS, REPORT } from './paths.js';
const captures = [];
const toolObservations = [];
function result(e, answer, tools = [], stop = 'end_turn') {
  return { turnId: e.turnId, index: e.index, answer, toolUses: tools, stopReason: stop, usage: null };
}
export function register(on) {
  // my-privacy is prepended, so this observer runs after its preparation and
  // before the actual native tool. It records only comparisons, never paths.
  on('tool.call', async ($, e, next) => {
    const call = CALLS[toolObservations.length];
    toolObservations.push({
      expectedTool: e.tool === call?.name,
      aliasPathUnchanged: call?.name === 'Bash'
        ? e.command === call.input.command
        : e.file_path === call?.input.file_path,
      originalPathAbsent: !String(e.command ?? e.file_path ?? '').includes('chenxinghe')
        && !String(e.command ?? e.file_path ?? '').includes('cedarbyte'),
    });
    return next(e);
  });
  on('turn.step', async function* ($, e) {
    const messages = await $.session.messages({ as: 'api' });
    const tools = messages.flatMap(m => Array.isArray(m.content)
      ? m.content.filter(b => b.type === 'tool_result') : []);
    const last = tools[tools.length - 1];
    const text = last ? JSON.stringify(last.content) : '';
    if (e.index > 0) captures.push({
      resultExists: !!last,
      succeeded: last?.is_error !== true && !text.includes('Local privacy guard'),
      companyAliasVisible: text.includes('Harborwave'),
      beforeMarkerVisible: text.includes('Version: before'),
      afterMarkerVisible: text.includes('Version: after'),
      rawOriginalAbsent: !/chenxinghe|cedarbyte/i.test(text),
      pathAmbiguous: text.includes('AMBIGUOUS'),
      unsupportedAliasCommand: text.includes('UNSUPPORTED_ALIAS_COMMAND'),
      complexAliasCommand: text.includes('COMPLEX_ALIAS_COMMAND'),
      missionMarkerVisible: text.includes('OFFLINE_MISSION_MARKER'),
      notesMarkerVisible: text.includes('OFFLINE_NOTES_MARKER'),
      resourcesMarkerVisible: text.includes('OFFLINE_RESOURCES_MARKER'),
      learningRecordMarkerVisible: text.includes('OFFLINE_LEARNING_RECORD_MARKER'),
      loopHeaderVisible: text.includes('=== learning-records/day-01.md'),
      semicolonTailMarkerVisible: text.includes('OFFLINE_SEMICOLON_TAIL_MARKER'),
    });
    const call = CALLS[e.index];
    if (!call) {
      const conversation = JSON.stringify(messages);
      await $.fs.write(REPORT, JSON.stringify({
        complete: true,
        captures,
        toolObservations,
        modelConversationHasNoOriginals: !/chenxinghe|cedarbyte/i.test(conversation),
      }));
      yield { kind: 'text', index: 0, text: 'OFFLINE_SYMLINK_AUDIT_COMPLETE' };
      yield { kind: 'stop', stopReason: 'end_turn', usage: null };
      return result(e, 'OFFLINE_SYMLINK_AUDIT_COMPLETE');
    }
    yield { kind: 'tool', index: 0, id: `toolu_symlink_${e.index}`, name: call.name };
    yield { kind: 'input', index: 0, json: JSON.stringify(call.input) };
    yield { kind: 'stop', stopReason: 'tool_use', usage: null };
    return result(e, '', [call], 'tool_use');
  });
}
'''


def main():
    os.umask(0o077)
    cli = shutil.which('claude')
    report = {
        'prerequisites': {
            'macOS': sys.platform == 'darwin',
            'sandboxAvailable': SANDBOX.is_file(),
            'claudeAvailable': cli is not None,
            'productionPluginAvailable': (PRODUCTION / '.claude-plugin/plugin.json').is_file(),
        },
        'execution': {
            'networkDenied': True,
            'syntheticFixturesOnly': True,
            'isolatedConfiguration': True,
            'processSucceeded': False,
            'mockCompleted': False,
            'timedOut': False,
        },
        'passed': False,
    }
    if all(report['prerequisites'].values()):
        try:
            with tempfile.TemporaryDirectory(prefix='my-privacy-symlink-e2e-') as directory:
                workspace = Path(directory)
                real_home = workspace / 'chenxinghe'
                real_project = real_home / 'Projects/cedarbyte'
                real_project.mkdir(parents=True)
                alias_home = workspace / 'ryanchen'
                alias_home.symlink_to(real_home, target_is_directory=True)
                company_link = real_home / 'Projects/harborwave'
                company_link.symlink_to(real_project, target_is_directory=True)
                alias_project = alias_home / 'Projects/harborwave'
                source = 'Version: before\nCompany: Cedarbyte\nShort alias: rc\n'
                (real_project / 'config.txt').write_text(source)
                for name in ('learning-records', 'lessons', 'reference', 'assets', 'notebooks'):
                    (real_project / name).mkdir()
                for filename, marker in (
                    ('MISSION.md', 'OFFLINE_MISSION_MARKER'),
                    ('NOTES.md', 'OFFLINE_NOTES_MARKER'),
                    ('RESOURCES.md', 'OFFLINE_RESOURCES_MARKER'),
                    ('learning-records/day-01.md', 'OFFLINE_LEARNING_RECORD_MARKER'),
                ):
                    (real_project / filename).write_text(marker + '\n')
                alias = str(alias_project)
                calls = [
                    {'name': 'Bash', 'input': {
                        'command': f'sed -n 1,4p {alias}/config.txt',
                        'description': 'Read a synthetic fixture through native symlinks',
                    }},
                    {'name': 'Read', 'input': {'file_path': alias + '/config.txt'}},
                    {'name': 'Write', 'input': {
                        'file_path': alias + '/created.txt',
                        'content': 'Version: before\nCompany: Harborwave\nShort alias: rc\n',
                    }},
                    {'name': 'Edit', 'input': {
                        'file_path': alias + '/created.txt',
                        'old_string': 'Version: before', 'new_string': 'Version: after',
                    }},
                    {'name': 'Bash', 'input': {
                        'command': f'''cd {alias} && python3 - <<'EOF'
from pathlib import Path
p = Path('config.txt')
s = p.read_text().replace('Version: before', 'Version: after')
s += 'Script literals: rc Harborwave\\n'
p.write_text(s)
EOF
sed -n 1,5p config.txt''',
                        'description': 'Edit a synthetic fixture through a native symlink directory',
                    }},
                    {'name': 'Read', 'input': {'file_path': alias + '/created.txt'}},
                    {'name': 'Bash', 'input': {
                        'command': f'cd {alias}; cat MISSION.md NOTES.md RESOURCES.md; '
                            'ls -la learning-records lessons reference assets notebooks; '
                            'for f in learning-records/*.md; do echo "=== $f"; cat "$f"; done',
                        'description': 'Read synthetic project notes using the semicolon command shape',
                    }},
                    {'name': 'Bash', 'input': {
                        'command': f'cd {alias}; false; printf "%s\\n" OFFLINE_SEMICOLON_TAIL_MARKER',
                        'description': 'Verify semicolons preserve execution after a failed shell command',
                    }},
                ]
                config = workspace / 'config'
                config.mkdir(mode=0o700)
                # Snapshot production to keep the single run internally consistent.
                plugin = workspace / 'my-privacy'
                shutil.copytree(PRODUCTION, plugin)
                mock = workspace / 'mock'
                (mock / '.claude-plugin').mkdir(parents=True)
                (mock / 'hooks').mkdir()
                (mock / '.claude-plugin/plugin.json').write_text(json.dumps({
                    'name': 'offline-symlink-audit', 'version': '0.1.0',
                    'description': 'Offline synthetic alias symlink regression',
                }))
                (mock / 'hooks/hooks.json').write_text('{"modules":["./register.js"]}')
                (mock / 'hooks/register.js').write_text(MOCK)
                (mock / 'hooks/paths.js').write_text(
                    'export const CALLS = ' + json.dumps(calls) + ';\n'
                    'export const REPORT = ' + json.dumps(str(workspace / 'audit.json')) + ';\n'
                )
                permitted = ('PATH', 'HOME', 'USER', 'LOGNAME', 'TMPDIR', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TERM')
                env = {key: value for key, value in os.environ.items() if key in permitted}
                env.update({
                    'CLAUDE_MY_PRIVACY_CONFIG': str(write_config(workspace)), 'CLAUDE_CONFIG_DIR': str(config),
                    'ANTHROPIC_API_KEY': 'offline-audit-placeholder',
                    'DISABLE_TELEMETRY': '1', 'DISABLE_ERROR_REPORTING': '1',
                    'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1',
                })
                command = [
                    str(SANDBOX), '-p', '(version 1)(allow default)(deny network*)', cli,
                    '--setting-sources', '', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
                    '--settings', '{"prependPlugins":["my-privacy@inline"]}',
                    '--dangerously-skip-permissions', '--tools', 'Read,Write,Edit,Bash',
                    '--plugin-dir', str(plugin), '--plugin-dir', str(mock),
                    '-p', 'Perform the offline synthetic symlink regression.',
                ]
                run = subprocess.run(command, cwd=workspace, env=env, capture_output=True,
                                     text=True, timeout=55, check=False)
                report['execution']['processSucceeded'] = run.returncode == 0
                report['execution']['mockCompleted'] = 'OFFLINE_SYMLINK_AUDIT_COMPLETE' in run.stdout
                report['execution']['moduleLoadError'] = 'Failed to load' in run.stderr or 'Failed to load' in run.stdout
                report['execution']['requestGuardBlocked'] = 'Local privacy guard stopped' in run.stdout
                audit_file = workspace / 'audit.json'
                audit = json.loads(audit_file.read_text()) if audit_file.exists() else {}
                captures = audit.get('captures', [])
                observations = audit.get('toolObservations', [])
                report['captures'] = captures
                report['toolObservations'] = observations
                created = real_project / 'created.txt'
                created_text = created.read_text() if created.is_file() else ''
                config_text = (real_project / 'config.txt').read_text()
                report['checks'] = {
                    'completed': audit.get('complete') is True,
                    'twoSymlinksResolveToRealProject': alias_home.is_symlink() and company_link.is_symlink()
                        and alias_project.resolve() == real_project.resolve(),
                    'allEightToolResultsSucceeded': len(captures) == 8 and all(row.get('resultExists') and row.get('succeeded') for row in captures),
                    'standaloneSedWorksWithoutCd': len(captures) > 0 and captures[0].get('succeeded')
                        and captures[0].get('beforeMarkerVisible') and captures[0].get('companyAliasVisible'),
                    'readWorksThroughDoubleAlias': len(captures) > 1 and captures[1].get('succeeded')
                        and captures[1].get('beforeMarkerVisible') and captures[1].get('companyAliasVisible'),
                    'allNativeToolPathsRetainAliases': len(observations) == 8
                        and all(all(row.values()) for row in observations),
                    'newFileWrittenAtRealTarget': created.is_file()
                        and (alias_project / 'created.txt').resolve() == created.resolve(),
                    'newFileCompanyRestored': 'Company: Cedarbyte' in created_text,
                    'editAppliedAtRealTarget': 'Version: after' in created_text and 'Version: before' not in created_text,
                    'heredocAppliedAtRealTarget': 'Version: after' in config_text and 'Version: before' not in config_text,
                    'scriptLiteralsUnchanged': 'Script literals: rc Harborwave' in config_text,
                    'shortAliasLiteralUnchanged': 'Short alias: rc' in created_text and 'Short alias: rc' in config_text,
                    'sourceCompanyUnchanged': 'Company: Cedarbyte' in config_text,
                    'finalReadShowsUpdatedFile': len(captures) > 5 and captures[5].get('succeeded')
                        and captures[5].get('afterMarkerVisible') and captures[5].get('companyAliasVisible'),
                    'semicolonProjectReadAndLoopSucceed': len(captures) > 6 and captures[6].get('succeeded')
                        and all(captures[6].get(key) for key in ('missionMarkerVisible', 'notesMarkerVisible',
                            'resourcesMarkerVisible', 'learningRecordMarkerVisible', 'loopHeaderVisible')),
                    'semicolonProjectCommandReachesNativeToolByteForByte': len(observations) > 6
                        and observations[6].get('aliasPathUnchanged') is True,
                    'semicolonTailRunsAfterFalse': len(captures) > 7 and captures[7].get('succeeded')
                        and captures[7].get('semicolonTailMarkerVisible'),
                    'semicolonFalseCommandReachesNativeToolByteForByte': len(observations) > 7
                        and observations[7].get('aliasPathUnchanged') is True,
                    'modelToolResultsContainNoOriginals': bool(captures) and all(row.get('rawOriginalAbsent') for row in captures),
                    'modelConversationContainsNoOriginals': audit.get('modelConversationHasNoOriginals') is True,
                }
                report['passed'] = report['execution']['processSucceeded'] and report['execution']['mockCompleted'] \
                    and all(report['checks'].values())
        except subprocess.TimeoutExpired:
            report['execution']['timedOut'] = True
        except (OSError, ValueError, KeyError, subprocess.SubprocessError):
            # Never emit child output, fixture contents, paths, or exception strings.
            report['execution']['failedBeforeCompleteReport'] = True
    (ROOT / 'evidence').mkdir(exist_ok=True)
    (ROOT / 'evidence/symlinks-latest-summary.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
