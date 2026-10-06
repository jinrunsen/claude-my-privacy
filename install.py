#!/usr/bin/env python3
"""Install only this local marketplace, retaining private configuration backups."""
from datetime import datetime
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
PLUGIN = ROOT / 'plugins' / 'my-privacy'
HOME = Path.home()
CLI = HOME / '.local/bin/claude'


def command(*args):
    env = dict(os.environ, CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1')
    subprocess.run([str(CLI), *args], check=True, env=env)


def main():
    version = subprocess.check_output([str(CLI), '--version'], text=True)
    match = re.search(r'(\d+)\.(\d+)\.(\d+)', version)
    if not match or tuple(map(int, match.groups())) < (2, 1, 288):
        raise SystemExit('Claude Code 2.1.288 or newer is required; revalidate after upgrades.')
    ROOT.chmod(0o700)
    command('plugin', 'validate', '--strict', str(PLUGIN))
    command('plugin', 'validate', '--strict', str(ROOT))
    backup = HOME / '.local/state/claude-my-privacy' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup.mkdir(parents=True, mode=0o700)
    os.chmod(backup.parent, 0o700)
    for name in ['settings.json', 'plugins/known_marketplaces.json', 'plugins/installed_plugins.json']:
        source = HOME / '.claude' / name
        if source.is_file():
            target = backup / name.replace('/', '--')
            shutil.copyfile(source, target)
            target.chmod(0o600)
    command('plugin', 'marketplace', 'add', str(ROOT), '--scope', 'user')
    registry_path = HOME / '.claude/plugins/installed_plugins.json'
    registry = json.loads(registry_path.read_text()) if registry_path.exists() else {}
    entries = registry.get('plugins', {}).get('my-privacy@my-privacy-marketplace', [])
    action = 'update' if any(entry.get('scope') == 'user' for entry in entries) else 'install'
    command('plugin', action, 'my-privacy@my-privacy-marketplace', '--scope', 'user')
    registry = json.loads(registry_path.read_text())
    for entry in registry.get('plugins', {}).get('my-privacy@my-privacy-marketplace', []):
        if entry.get('scope') == 'user':
            installed = Path(entry['installPath'])
            installed.chmod(0o700)
            for name in ['config.js', 'lib/privacy.js']:
                (installed / name).chmod(0o600)
    path = HOME / '.claude/settings.json'
    raw = path.read_bytes()
    settings = json.loads(raw)
    # This previously enabled compactor can send context to a separate service.
    # Leave it installed but disabled; original configuration is in the backup.
    enabled = settings.setdefault('enabledPlugins', {})
    disabled = []
    if enabled.get('fast-jev-compaction@fast-jev-compaction'):
        enabled['fast-jev-compaction@fast-jev-compaction'] = False
        disabled.append('fast-jev-compaction@fast-jev-compaction')
    # Supported for personal plans without managed policy. Claude ignores this
    # user setting where an organization's policy owns Mod ordering.
    plugin_id = 'my-privacy@my-privacy-marketplace'
    enabled[plugin_id] = True
    previous_order = settings.get('prependPlugins', [])
    if not isinstance(previous_order, list) or not all(isinstance(item, str) for item in previous_order):
        raise RuntimeError('Invalid prependPlugins setting. Backup retained; refusing overwrite.')
    settings['prependPlugins'] = [plugin_id, *[item for item in previous_order if item != plugin_id]]
    settings.setdefault('env', {}).update({
        'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1',
        'DISABLE_TELEMETRY': '1',
        'DISABLE_ERROR_REPORTING': '1',
        'DISABLE_FEEDBACK_COMMAND': '1',
    })
    fd, temporary = tempfile.mkstemp(prefix='.my-privacy-settings-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as handle:
            os.fchmod(handle.fileno(), 0o600)
            json.dump(settings, handle, indent=2, ensure_ascii=False)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        if path.read_bytes() != raw:
            raise RuntimeError('Settings changed concurrently. Backup retained; refusing overwrite.')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    report = {'claudeVersion': version.strip(), 'source': str(PLUGIN),
              'enabled': 'my-privacy@my-privacy-marketplace',
              'requestedFirst': plugin_id,
              'disabledPlugins': disabled, 'settingsBackup': str(backup)}
    target = backup / 'installation.json'
    target.write_text(json.dumps(report, indent=2) + '\n')
    target.chmod(0o600)
    print(json.dumps(report, indent=2))
    print('Start a NEW Claude session and run /my-privacy-status. Existing sessions are not reconfigured by this installer.')


if __name__ == '__main__':
    main()
