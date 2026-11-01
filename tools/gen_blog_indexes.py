#!/usr/bin/env python3
# Regenerate the managed blog regions in writing.html, sitemap.xml and llms.txt from the set of
# approved posts in content/blog/*.md. ONLY the text between the <!-- BLOG:START --> and
# <!-- BLOG:END --> markers is rewritten; every hand-authored essay, the MarTech archive, and every
# other page or line is left exactly as it is. Idempotent and set-based: it rebuilds from whatever
# posts exist now, so unpublishing a post (removing its .md) drops its references from all three.
# Website Build owns this; it runs in CI on every deploy and is never fed Marketing-authored HTML.
import glob, re, html, pathlib, sys

START, END = "<!-- BLOG:START -->", "<!-- BLOG:END -->"

def smarten(t):
    t = t.replace("'", "’"); o = []
    for i, c in enumerate(t):
        if c == '"':
            p = t[i-1] if i > 0 else ' '
            o.append('“' if (i == 0 or p.isspace() or p in '([{’') else '”')
        else:
            o.append(c)
    return ''.join(o)

esc = lambda s: html.escape(s, quote=False)

def parse_fm(path):
    src = pathlib.Path(path).read_text(encoding='utf-8')
    fm = src.split('\n---\n', 1)[0]
    fm = fm.split('---\n', 1)[1] if fm.startswith('---') else fm
    meta = {}
    for line in fm.split('\n'):
        line = line.rstrip()
        if not line or ':' not in line:
            continue
        k, _, v = line.partition(':'); k = k.strip(); v = v.strip()
        if v == '""':
            v = ''
        elif len(v) >= 2 and v[0] == '"' and v[-1] == '"':
            v = v[1:-1]
        meta[k] = v
    return meta

def load_posts(root):
    posts = [parse_fm(p) for p in glob.glob(f"{root}/content/blog/*.md")]
    # newest first by publish_time (ISO strings sort correctly)
    posts.sort(key=lambda m: m.get('publish_time', ''), reverse=True)
    return posts

def replace_region(path, new):
    s = pathlib.Path(path).read_text(encoding='utf-8')
    pat = re.compile(re.escape(START) + r'.*?' + re.escape(END), re.S)
    if not pat.search(s):
        sys.exit(f"markers not found in {path}")
    pathlib.Path(path).write_text(pat.sub(lambda _: START + new + END, s), encoding='utf-8')

def main():
    root = sys.argv[1] if len(sys.argv) > 1 else '.'
    posts = load_posts(root)

    # writing.html — a "Recent writing" section of feature cards, or nothing when there are no posts
    if posts:
        cards = []
        for i, m in enumerate(posts):
            mt = ' style="margin-top:16px"' if i > 0 else ''
            cards.append(
                f'      <div class="feature"{mt}>\n'
                f'        <h3><a href="writing/{m["slug"]}">{esc(smarten(m["title"]))}</a></h3>\n'
                f'        <p>{esc(smarten(m.get("excerpt", "")))}</p>\n'
                f'      </div>'
            )
        region = ('\n  <section style="padding-top:56px">\n'
                  '    <div class="wrap"><div class="narrow" style="margin:0 auto">\n'
                  '      <p class="eyebrow">Recent writing</p>\n'
                  + '\n'.join(cards) + '\n'
                  '    </div></div>\n  </section>\n')
    else:
        region = '\n'
    replace_region(f"{root}/writing.html", region)

    # sitemap.xml — one <url> per post at the pretty /writing/<slug> URL
    if posts:
        urls = [f'  <url><loc>https://ryanphelan.com/writing/{m["slug"]}</loc><lastmod>{(m.get("publish_time","") or "")[:10]}</lastmod></url>' for m in posts]
        region = '\n' + '\n'.join(urls) + '\n  '
    else:
        region = '\n  '
    replace_region(f"{root}/sitemap.xml", region)

    # llms.txt — one "- [Title](url): excerpt" line per post, under ## Writing
    if posts:
        lines = [f'- [{m["title"]}](https://ryanphelan.com/writing/{m["slug"]}): {m.get("excerpt","")}' for m in posts]
        region = '\n' + '\n'.join(lines) + '\n'
    else:
        region = '\n'
    replace_region(f"{root}/llms.txt", region)

    print(f"regenerated blog regions from {len(posts)} post(s): {[m.get('slug') for m in posts]}")

if __name__ == '__main__':
    main()
