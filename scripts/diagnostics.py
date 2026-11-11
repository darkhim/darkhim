#!/usr/bin/env python3
"""Render a Fallout-style terminal SVG with GitHub contribution stats.

Usage: GITHUB_TOKEN=... python3 diagnostics.py <login> <output.svg>
Only stdlib; works with the Actions GITHUB_TOKEN.
"""
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timezone
from html import escape

QUERY = """
query($login: String!) {
  user(login: $login) {
    createdAt
    followers { totalCount }
    repositories(ownerAffiliations: OWNER, privacy: PUBLIC) { totalCount }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount date } }
      }
    }
  }
}
"""

GREEN = "#3cff6e"
DIM = "#1f9c41"


def fetch(login: str, token: str) -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "diagnostics-svg"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if payload.get("errors"):
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    return payload["data"]["user"]


def streaks(days: list[dict]) -> tuple[int, int]:
    longest = run = 0
    for d in days:
        run = run + 1 if d["contributionCount"] > 0 else 0
        longest = max(longest, run)
    # current streak: today may still be empty, so don't break on it
    current = 0
    today = date.today().isoformat()
    for d in reversed(days):
        if d["contributionCount"] > 0:
            current += 1
        elif d["date"] == today:
            continue
        else:
            break
    return current, longest


def dotted(label: str, value: str, width: int = 34) -> str:
    return f"{label} {'.' * max(2, width - len(label) - len(value) - 2)} {value}"


def render(u: dict) -> str:
    cc = u["contributionsCollection"]
    cal = cc["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    cur, longest = streaks(days)
    years = datetime.now(timezone.utc).year - int(u["createdAt"][:4])

    rows = [
        ("CONTRIBUTIONS / 12 MO", f"{cal['totalContributions']:,}"),
        ("  PRIVATE OPERATIONS", f"{cc['restrictedContributionsCount']:,}"),
        ("  COMMITS", f"{cc['totalCommitContributions']:,}"),
        ("  PULL REQUESTS", f"{cc['totalPullRequestContributions']:,}"),
        ("CURRENT STREAK", f"{cur} DAY" + ("" if cur == 1 else "S")),
        ("LONGEST STREAK", f"{longest} DAY" + ("" if longest == 1 else "S")),
        ("YEARS IN THE FIELD", str(years)),
    ]

    # weekly bars, last 26 weeks
    weeks = cal["weeks"][-26:]
    totals = [sum(d["contributionCount"] for d in w["contributionDays"]) for w in weeks]
    peak = max(totals) or 1
    bx, by, bw, bh, gap = 550, 92, 12, 140, 2
    bars = []
    for i, t in enumerate(totals):
        h = max(2, round(bh * t / peak)) if t else 2
        op = "1" if t else ".35"
        bars.append(
            f'<rect x="{bx + i * (bw + gap)}" y="{by + bh - h}" width="{bw}" height="{h}" '
            f'fill="{GREEN}" opacity="{op}" class="bar" style="animation-delay:{0.6 + i * 0.04:.2f}s"/>'
        )

    lines = []
    for i, (k, v) in enumerate(rows):
        sub = k.startswith("  ")
        cls = "dim" if sub else ""
        x = 64 if sub else 40
        txt = dotted(k.strip(), v, 32 if sub else 34)
        lines.append(
            f'<text x="{x}" y="{96 + i * 26}" class="{cls} ln" style="animation-delay:{0.3 + i * 0.25:.2f}s">'
            f"{escape(txt)}</text>"
        )

    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 300" width="960" height="300" role="img" aria-label="GitHub contribution diagnostics">
  <defs>
    <radialGradient id="crt" cx="50%" cy="50%" r="75%">
      <stop offset="0%" stop-color="#0f2a14"/><stop offset="70%" stop-color="#07160a"/><stop offset="100%" stop-color="#020703"/>
    </radialGradient>
    <pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="2" fill="#000" opacity="0.28"/></pattern>
    <filter id="glow" x="-10%" y="-30%" width="120%" height="160%">
      <feGaussianBlur stdDeviation="2" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <style>
    text{{font-family:'VT323','Share Tech Mono','Fira Mono','Courier New',monospace;fill:{GREEN};font-size:19px;letter-spacing:1px;white-space:pre}}
    .dim{{fill:{DIM}}} .h{{font-size:22px;font-weight:bold}} .s{{font-size:15px}}
    .ln{{opacity:0;animation:on .01s forwards}}
    .bar{{transform-box:fill-box;transform-origin:bottom;transform:scaleY(0);animation:grow .5s ease-out forwards}}
    @keyframes on{{to{{opacity:1}}}}
    @keyframes grow{{to{{transform:scaleY(1)}}}}
  </style>
  <rect width="960" height="300" rx="18" fill="url(#crt)"/>
  <g filter="url(#glow)">
    <text x="40" y="44" class="h">&gt; RUN DIAGNOSTICS.EXE --USER {escape(u.get('login', 'darkhim').upper())}</text>
    <line x1="40" y1="58" x2="920" y2="58" stroke="{DIM}" stroke-dasharray="6 4"/>
    {''.join(lines)}
    <text x="{bx}" y="{by - 10}" class="dim s">WEEKLY ACTIVITY // LAST 26 WEEKS</text>
    {''.join(bars)}
    <line x1="{bx}" y1="{by + bh + 1}" x2="{bx + 26 * (bw + gap) - gap}" y2="{by + bh + 1}" stroke="{DIM}"/>
    <text x="40" y="282" class="dim s">LAST SYNC {updated} · ALL SYSTEMS NOMINAL</text>
  </g>
  <rect width="960" height="300" rx="18" fill="url(#scan)"/>
  <rect x="3" y="3" width="954" height="294" rx="16" fill="none" stroke="{DIM}" stroke-opacity=".55" stroke-width="2"/>
</svg>
"""


def main() -> None:
    login, out = sys.argv[1], sys.argv[2]
    token = os.environ["GITHUB_TOKEN"]
    user = fetch(login, token)
    user["login"] = login
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(render(user))


if __name__ == "__main__":
    main()
