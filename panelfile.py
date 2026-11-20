#!/usr/bin/env python3
"""Panel helpers: download/upload single server files (Pterodactyl 2-step upload)."""
import json, os, sys, subprocess, urllib.request, urllib.parse, uuid

BASE = 'https://panel.mineidhost.com/api/client/servers/5a7d17e3'
_raw = open(os.path.expanduser('~/.config/mcops/panel.key')).read().strip()
KEY = _raw.split('=', 1)[1].strip().strip('\'"') if '=' in _raw else _raw
UA = 'Mozilla/5.0 (X11; Linux x86_64) Chrome/141 Safari/537.36'
HDR = {'Authorization': 'Bearer ' + KEY, 'User-Agent': UA, 'Accept': 'application/json'}


def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={**HDR, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(r, timeout=120) as resp:
        raw = resp.read()
        return json.loads(raw) if raw.strip() else {}


def listing(d='/'):
    return req('GET', '/files/list?directory=' + urllib.parse.quote(d)).get('data', []) or []


def exists(remote):
    parent, name = remote.rsplit('/', 1)
    return name in [f['attributes']['name'] for f in listing(parent or '/')]


def download(remote, local):
    d = req('GET', '/files/download?file=' + urllib.parse.quote(remote, safe=''))
    attrs = d.get('attributes', d)
    link = attrs.get('url') or attrs.get('download_url')
    os.makedirs(os.path.dirname(local) or '.', exist_ok=True)
    open(local, 'wb').write(urllib.request.urlopen(link, timeout=180).read())
    return local


def _delete(remote):
    root, name = remote.rsplit('/', 1)
    return req('POST', '/files/delete', {'root': root or '/', 'files': [name]})


def upload(local, remote):
    """Upload under a unique temp name in panel root, then rename over the target."""
    tmp = 'zzupl-%s.tmp' % uuid.uuid4().hex[:10]
    s = req('GET', '/files/upload')
    url = s['attributes']['url']
    out = subprocess.run(['curl', '-sS', '--max-time', '180', '-F', 'files=@%s;filename=%s' % (local, tmp), url],
                         capture_output=True, text=True)
    if out.returncode != 0:
        return 'curl failed: ' + out.stderr[:300]
    if not exists('/' + tmp):
        return 'upload missing: ' + out.stdout[:200] + out.stderr[:200]
    if exists(remote):
        _delete(remote)
    r = req('PUT', '/files/rename', {'root': '/', 'files': [{'from': tmp, 'to': remote.lstrip('/')}]})
    return 'ok=%s remote=%s size=%s' % (exists(remote), remote, os.path.getsize(local))


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'get':
        print(download(sys.argv[2], sys.argv[3]))
    elif cmd == 'upload':
        print(upload(sys.argv[2], sys.argv[3]))
    elif cmd == 'ls':
        for f in sorted(listing(sys.argv[2] if len(sys.argv) > 2 else '/'), key=lambda x: x['attributes']['name']):
            a = f['attributes']
            print(('d' if a.get('is_file') is False else '-'), str(a.get('size', 0)).rjust(9), a['name'])
