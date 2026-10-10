"""Draws "lights on": the last few public repos I pushed to, as a night street.

Run by .github/workflows/lights.yml. Needs GITHUB_TOKEN in env (read-only public data).
Writes assets/lights-{dark,light}.svg and rewrites the README block between the lights markers.
"""
import datetime as dt
import json
import math
import os
import pathlib
import re
import urllib.request
from xml.dom import minidom

USER = os.environ.get("LIGHTS_USER", "Fuheshka")
COUNT = 4
DAYS = 30
ROOT = pathlib.Path(__file__).resolve().parent.parent

SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
# accents are the peak keyframes of the rainbow city animation
THEMES = {
    "dark": dict(fg="#e6edf3", muted="#8b949e", line="#30363d", wall="#161b22", side="#0f1319", off="#21262d",
                 accents=["#40bdbf", "#bf40bd", "#bfbd40"]),
    "light": dict(fg="#1f2328", muted="#59636e", line="#d0d7de", wall="#eaeef2", side="#d8dee4", off="#ffffff",
                  accents=["#1e8486", "#a3349f", "#8a8820"]),
}


def api(path):
    req = urllib.request.Request(f"https://api.github.com/{path}", headers={
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def pick_repos():
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    picked = []
    for repo in api(f"users/{USER}/repos?type=owner&sort=pushed&per_page=30"):
        if repo["name"].lower() == USER.lower() or repo["archived"]:
            continue
        # shortcut: counts at most 100 commits per repo, enough for building height on a log scale
        commits = len(api(f"repos/{repo['full_name']}/commits?author={USER}&since={since}&per_page=100"))
        if repo["fork"] and commits == 0:
            continue  # someone else's project I only forked
        picked.append(dict(name=repo["name"], url=repo["html_url"], lang=repo["language"] or "", commits=commits))
        if len(picked) == COUNT:
            break
    return picked


def building(x, base, w, h, c, accent, commits):
    """Isometric-ish tower: front wall, right side, roof; windows lit one per commit."""
    d = 14  # side depth
    top = base - h
    parts = [f'<polygon points="{x+w},{top} {x+w+d},{top-8} {x+w+d},{base-8} {x+w},{base}" fill="{c["side"]}"/>',
             f'<polygon points="{x},{top} {x+d},{top-8} {x+w+d},{top-8} {x+w},{top}" fill="{accent}"/>',
             f'<rect x="{x}" y="{top}" width="{w}" height="{h}" fill="{c["wall"]}" stroke="{c["line"]}"/>']
    cols, size, gap = 4, 8, 6
    rows = max(1, int((h - 14) // (size + gap)))
    lit = min(commits, cols * rows)
    i = 0
    for r in range(rows - 1, -1, -1):  # fill from the ground up
        for k in range(cols):
            on = i < lit
            parts.append(f'<rect x="{x + 10 + k * (size + gap)}" y="{top + 12 + r * (size + gap)}" '
                         f'width="{size}" height="{size}" fill="{accent if on else c["off"]}"/>')
            i += 1
    return "".join(parts)


def render(repos, c):
    W, base, w = 720, 196, 70
    step = W / len(repos)
    top = max(1, max(r["commits"] for r in repos))
    body = [f'<line x1="0" y1="{base + .5}" x2="{W}" y2="{base + .5}" stroke="{c["line"]}"/>']
    for i, r in enumerate(repos):
        accent = c["accents"][i % 3]
        x = round(i * step + (step - w - 14) / 2)
        h = round(60 + 110 * math.sqrt(r["commits"] / top))
        cx = x + (w + 14) / 2
        name = r["name"] if len(r["name"]) <= 18 else r["name"][:17] + "…"
        body.append(building(x, base, w, h, c, accent, r["commits"]))
        body.append(f'<text x="{cx}" y="{base + 28}" text-anchor="middle" font-family="{SANS}" font-size="16" '
                    f'font-weight="600" fill="{c["fg"]}">{name}</text>')
        meta = " · ".join(filter(None, [r["lang"], f'{r["commits"]} commits']))
        body.append(f'<text x="{cx}" y="{base + 48}" text-anchor="middle" font-family="{MONO}" font-size="12" '
                    f'fill="{c["muted"]}">{meta}</text>')
    label = "lights on: " + ", ".join(r["name"] for r in repos)
    data = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} 256" width="{W}" height="256" role="img" '
            f'aria-label="{label}"><title>{label}</title>{"".join(body)}</svg>\n')
    minidom.parseString(data)  # fail loudly on malformed XML
    assert len(data.encode()) < 50_000
    return data


def readme_block(repos):
    links = " &nbsp;·&nbsp; ".join(f'<a href="{r["url"]}">{r["name"]}</a>' for r in repos)
    return f"""<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/lights-dark.svg">
  <img src="assets/lights-light.svg" width="720" alt="Lights on: the repos I pushed to most recently">
</picture>
<br>
<sub>lights on right now: what I touched last, one lit window per commit in the past {DAYS} days</sub>
<br>
<sub>{links}</sub>"""


def main():
    repos = pick_repos()
    assert repos, "no repos found"
    for theme, c in THEMES.items():
        (ROOT / "assets" / f"lights-{theme}.svg").write_text(render(repos, c))
    readme = ROOT / "README.md"
    text, n = re.subn(r"(<!-- lights:start -->\n).*?(<!-- lights:end -->)",
                      lambda m: m.group(1) + readme_block(repos) + "\n" + m.group(2), readme.read_text(), flags=re.S)
    assert n == 1, "lights markers missing in README.md"
    readme.write_text(text)
    for r in repos:
        print(f'{r["name"]:30} {r["commits"]:3} commits  {r["lang"]}')


if __name__ == "__main__":
    main()
