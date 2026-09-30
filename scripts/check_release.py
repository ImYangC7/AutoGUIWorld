#!/usr/bin/env python3
"""Scan release files without printing matched secrets or personal fields."""
from __future__ import annotations

import argparse
import ast
import hashlib
import ipaddress
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
CONNECTION = re.compile(
    r'\b(?:api_?base|base[_]url|api_?key|(?:\w+_)?app_?key|(?:\w+_)?app_?id|'
    r'llm[_]auth|llm[_]url|image[_]api[_]url|model[_]marker|make[_]image[_]auth|data[_]eval)\b', re.I)
PERSONAL_PATH = re.compile(r'/(?:Users|home)/[A-Za-z0-9_.-]+|/(?:taijifs|apdcephfs)[^\s]*', re.I)
EMAIL = re.compile(r'\b[\w.+-]+@([\w.-]+\.[A-Za-z]{2,})\b')
TOKEN = re.compile(
    r'\b(?:hf_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|'
    r'AKIA[0-9A-Z]{16})\b|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----')
SECRET_NAME = re.compile(r'(?:api.?key|app.?key|app.?id|secret|access.?token|password)$', re.I)
URL = re.compile(r'https?://[^\s\x22\x27<>`]+')
RESERVED_MAIL = {'example.com', 'example.org', 'example.net', 'example.invalid'}
FIXTURE_CATEGORIES = {'non-synthetic-email', 'personal-absolute-path'}


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def scan_text(filename, content):
    findings = set()
    for number, line in enumerate(content.splitlines(), 1):
        for category, pattern in [('provider-connection-field', CONNECTION),
                                  ('personal-absolute-path', PERSONAL_PATH),
                                  ('credential-like-token', TOKEN)]:
            if pattern.search(line):
                findings.add((number, category))
        for match in EMAIL.finditer(line):
            if match.group(1).lower() not in RESERVED_MAIL:
                findings.add((number, 'non-synthetic-email'))
        for match in URL.finditer(line):
            try:
                parsed = urlsplit(match.group())
                host = parsed.hostname or ''
                if parsed.username or parsed.password:
                    findings.add((number, 'credential-bearing-url'))
                try:
                    address = ipaddress.ip_address(host)
                except ValueError:
                    if host.endswith(('.internal', '.corp', '.local')):
                        findings.add((number, 'internal-host'))
                else:
                    if address.is_private and not address.is_loopback:
                        findings.add((number, 'private-network-host'))
            except ValueError:
                continue
    if filename.endswith('.py'):
        try:
            tree = ast.parse(content)
        except SyntaxError:
            findings.add((1, 'invalid-python-syntax'))
        else:
            for node in ast.walk(tree):
                if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                    continue
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if not any(SECRET_NAME.search(ast.unparse(target)) for target in targets):
                    continue
                value = node.value
                if isinstance(value, ast.Call) and len(value.args) > 1:
                    value = value.args[1]
                if isinstance(value, ast.Constant) and isinstance(value.value, str) and value.value:
                    if not re.search(r'YOUR_|SAMPLE_|EXAMPLE|placeholder', value.value, re.I):
                        findings.add((node.lineno, 'hardcoded-credential-default'))
    return [{'file': filename, 'line': line, 'category': category}
            for line, category in sorted(findings)]


def generated_file(filename):
    path = Path(filename)
    return (path.name.startswith('.env') and path.name != '.env.example') or (
        any(part in {'data', 'data_legacy', 'logs', 'backup', 'models', '.venv', '__pycache__'}
            for part in path.parts)
    ) or path.suffix.lower() in {'.pem', '.key', '.safetensors', '.pt', '.pyc'}


def classify_reviewed_fixture(filename, raw, findings, approvals):
    """Recognize reviewed sample content without exempting operational secrets."""
    approval = approvals.get(filename, {})
    if approval.get('sha256') != hashlib.sha256(raw).hexdigest():
        return findings, []
    accepted = FIXTURE_CATEGORIES.intersection(approval.get('categories', []))
    blocking, reviewed = [], []
    for finding in findings:
        if finding['category'] in accepted:
            reviewed.append(dict(finding, reason=approval['reason']))
        else:
            blocking.append(finding)
    return blocking, reviewed


def scan_files(revision=None):
    names = (git('ls-tree', '-r', '--name-only', '-z', revision) if revision else
             git('ls-files', '--cached', '--others', '--exclude-standard', '-z'))
    findings = []
    reviewed = []
    approvals = {}
    policy = ROOT / '.release-fixtures.json'
    if revision is None and policy.is_file():
        approvals = json.loads(policy.read_text())['files']
    count = 0
    for filename in sorted(set(names.decode().strip('\0').split('\0'))):
        if not filename:
            continue
        path = ROOT / filename
        if not revision and not path.is_file():
            continue
        count += 1
        if generated_file(filename):
            findings.append({'file': filename, 'line': 0, 'category': 'generated-or-private-file'})
        raw = git('show', f'{revision}:{filename}') if revision else path.read_bytes()
        try:
            text = raw.decode('utf-8')
        except UnicodeError:
            continue
        blocking, accepted = classify_reviewed_fixture(
            filename, raw, scan_text(filename, text), approvals)
        findings.extend(blocking)
        reviewed.extend(accepted)
    return count, findings, reviewed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history', action='store_true', help='Also check every reachable commit')
    parser.add_argument('--json', action='store_true', help='Print machine-readable locations')
    args = parser.parse_args()
    count, findings, reviewed = scan_files()
    report = {'files_scanned': count, 'findings': findings, 'reviewed_fixture_matches': reviewed}
    if args.history:
        history = []
        commits = git('rev-list', '--all').decode().splitlines()
        for revision in commits:
            _, found, _ = scan_files(revision)
            history.extend(dict(item, commit=revision) for item in found)
        report.update(commits_scanned=len(commits), history_findings=history)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for item in findings:
            print(f"{item['file']}:{item['line']}: {item['category']}")
        print(f"Scanned {count} files; {len(findings)} working-tree findings")
        print(f"Reviewed sample-content matches: {len(reviewed)}")
        if args.history:
            print(f"Scanned {len(commits)} commits; {len(history)} history findings")
    return int(bool(findings or report.get('history_findings')))


if __name__ == '__main__':
    raise SystemExit(main())
