"""Small SVG helpers for the offline Hemera architecture atlas."""
from html import escape as esc


def box(key, x, y, title, sub='', tone='blue', w=220, h=90, tag='CIBLE', lines=None):
    label = esc(title, quote=True)
    subtitles = lines or ([sub] if sub else [])
    body = ''.join(f'<text class="sub" x="{x+18}" y="{y+63+i*18}">{esc(t)}</text>' for i,t in enumerate(subtitles))
    return f'<g class="node {tone}" data-node="{esc(key)}" tabindex="0" role="button" aria-label="{label}" aria-pressed="false"><rect class="node-bg" x="{x}" y="{y}" width="{w}" height="{h}" rx="12"/><rect class="accent" x="{x}" y="{y+14}" width="4" height="{h-28}" rx="2"/><text class="tag" x="{x+18}" y="{y+19}">{esc(tag)}</text><text class="node-title" x="{x+18}" y="{y+42}">{esc(title)}</text>{body}</g>'


def lane(x, y, w, h, title, sub=''):
    return f'<rect class="lane" x="{x}" y="{y}" width="{w}" height="{h}" rx="16"/><text class="lane-title" x="{x+18}" y="{y+27}">{esc(title)}</text><text class="sub" x="{x+18}" y="{y+48}">{esc(sub)}</text>'


def path(key, points, tone='blue', dashed=False):
    dash=' stroke-dasharray="7 5"' if dashed else ''
    return f'<path data-edge="{esc(key)}" class="edge {tone}" d="{points}"{dash} marker-end="url(#ARROW)"/>'


def note(x,y,title,sub='',tone='muted'):
    return f'<text class="annotation {tone}" x="{x}" y="{y}">{esc(title)}</text><text class="sub" x="{x}" y="{y+21}">{esc(sub)}</text>'


def detail(title, summary, technical, state='Cible proposée', proof='08-plateforme-rust-sans-jvm.html', anchor=''):
    return dict(title=title,summary=summary,technical=technical,state=state,proof='../'+proof+('#'+anchor if anchor else ''))


def view(label, nodes, edges, caption):
    return dict(label=label,nodes=nodes.split(),edges=edges.split(),caption=caption)
