#!/usr/bin/env python3
import sys, json, html, re, hashlib, pathlib
def smarten(t):
    t=t.replace("'","’"); o=[]
    for i,c in enumerate(t):
        if c=='"':
            p=t[i-1] if i>0 else ' '
            o.append('“' if (i==0 or p.isspace() or p in '([{’') else '”')
        else: o.append(c)
    return ''.join(o)
esc=lambda s: html.escape(s,quote=False)
def linkify(e): return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', e)
def render_body(md):
    out=[]; ol=[]; ul=[]
    def flush():
        nonlocal ol,ul
        if ol: out.append('<ol>'+''.join(f'<li>{esc(smarten(x))}</li>' for x in ol)+'</ol>'); ol=[]
        if ul: out.append('<ul>'+''.join(f'<li>{esc(smarten(x))}</li>' for x in ul)+'</ul>'); ul=[]
    lines=md.split('\n'); i=0; pn=0
    while i<len(lines):
        ln=lines[i]
        if ln.startswith('```prompt'):
            flush(); j=i+1; buf=[]
            while j<len(lines) and lines[j]!='```': buf.append(lines[j]); j+=1
            pn+=1; out.append(f'<div class="prompt"><details><summary>Show the prompt</summary><pre id="prompt-{pn}">{esc(chr(10).join(buf))}</pre></details><button class="prompt-copy" data-copy="prompt-{pn}">Copy</button></div>'); i=j+1; continue
        if ln.startswith('## '): flush(); out.append(f'<h2>{esc(smarten(ln[3:]))}</h2>'); i+=1; continue
        if ln.startswith('### '): flush(); out.append(f'<h3>{esc(smarten(ln[4:]))}</h3>'); i+=1; continue
        if ln.startswith('- '):
            if ol: flush()
            ul.append(ln[2:]); i+=1; continue
        if not ln.strip(): flush(); i+=1; continue
        flush(); e=linkify(esc(smarten(ln))); out.append(f'<p>{e}</p>'); i+=1
    flush(); return '\n'.join(out)
def main():
    src=pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')
    fm,body=src.split('\n---\n',1); fm=fm.split('---\n',1)[1] if fm.startswith('---') else fm
    meta=json.loads(fm.strip())
    slug=meta['slug']; body_html=render_body(body.strip())
    url=f"https://ryanphelan.com/writing/{slug}"   # production canonical shape
    page=f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(meta.get('seo_title') or meta['title'])}</title>
<meta name="description" content="{esc(meta['meta_description'])}">
<link rel="canonical" href="{meta.get('canonical_url') or url}">
<meta property="og:title" content="{esc(meta.get('seo_title') or meta['title'])}">
<meta property="og:description" content="{esc(meta['meta_description'])}">
</head><body>
<article class="art"><h1>{esc(meta['title'])}</h1>
<p class="art-meta">By {esc(meta['author'])}</p>
<div class="art-body">
{body_html}
</div></article>
</body></html>
'''
    out=pathlib.Path('writing')/f'{slug}.html'; out.parent.mkdir(exist_ok=True)
    out.write_text(page,encoding='utf-8')
    print(out, 'bodyhash', 'sha256:'+hashlib.sha256(body_html.encode()).hexdigest())
if __name__=='__main__': main()
