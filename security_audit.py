"""Redacted working-tree/history secret scan and optional OSV lockfile audit.

Run with Back-End/.venv/Scripts/python.exe security_audit.py [--online].
Candidate values and Git content are never printed. Heuristic scan, not proof of absence.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
SKIP = {'node_modules', '.venv', '.backend-venv', '.git', '__pycache__',
        '.security-tools', '.test-state', 'dist', 'test-results'}
PATTERNS = {
    'private-key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'aws-access-key': re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    'github-token': re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})'),
    'google-api-key': re.compile(r'\bAIza[0-9A-Za-z_-]{35}\b'),
    'stripe-secret': re.compile(r'\bsk_live_[0-9A-Za-z]{20,}\b'),
    'stellar-secret': re.compile(r'\bS[A-Z2-7]{55}\b'),
    'literal-credential': re.compile(r'''(?i)(?:api[_-]?key|client[_-]?secret|secret[_-]?key|private[_-]?key|password)\s*[:=]\s*['"]([A-Za-z0-9_+/=-]{24,})['"]'''),
}


def candidates(name, text):
    results = []
    for number, line in enumerate(text.splitlines(), 1):
        for kind, pattern in PATTERNS.items():
            if pattern.search(line):
                results.append({'file': name, 'line': number, 'kind': kind})
    return results


def main():
    findings = []
    scanned = 0
    for directory, folders, files in os.walk(ROOT):
        folders[:] = [name for name in folders if name not in SKIP]
        for name in files:
            path = Path(directory) / name
            # Local server secrets are expected here; scan frontend env files for exposure.
            if path.parent == ROOT / 'Back-End' and name.startswith('.env'):
                continue
            if path.suffix.lower() not in {'.py', '.js', '.jsx', '.json', '.md', '.html', '.txt', '.yml', '.yaml', '.toml', '.env'} and not name.startswith('.env'):
                continue
            if path.stat().st_size > 2_000_000:
                continue
            text = path.read_text(encoding='utf-8', errors='replace')
            scanned += 1
            findings.extend(candidates(str(path.relative_to(ROOT)), text))
    git = shutil.which('git')
    history = {'status': 'unavailable', 'reason': 'No Git executable or repository metadata available.'}
    if git:
        probe = subprocess.run([git, '-C', str(ROOT), 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
        if probe.returncode == 0:
            history = {'status': 'scanned', 'commits': 0}
            commits = subprocess.check_output([git, '-C', str(ROOT), 'rev-list', '--all'], text=True).splitlines()
            for commit in commits:
                content = subprocess.check_output([git, '-C', str(ROOT), 'show', '--format=', commit], text=True, errors='replace')
                findings.extend(candidates('git-diff:' + commit, content))
            history['commits'] = len(commits)
    result = {'files_scanned': scanned, 'secret_candidates': findings, 'git_history': history}
    if '--online' in sys.argv:
        import requests
        packages = []
        for line in (ROOT / 'Back-End/requirements.lock.txt').read_text().splitlines():
            if '==' in line:
                name, version = line.strip().split('==', 1)
                packages.append({'package': {'name': name, 'ecosystem': 'PyPI'}, 'version': version})
        response = requests.post('https://api.osv.dev/v1/querybatch', json={'queries': packages}, timeout=45)
        response.raise_for_status()
        result['python_advisories'] = [
            {'package': item['package']['name'], 'version': item['version'], 'ids': [v['id'] for v in entry.get('vulns', [])]}
            for item, entry in zip(packages, response.json()['results']) if entry.get('vulns')
        ]
        result['python_packages_checked'] = len(packages)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
