"""Render the capstone's computed narrative as a self-contained paper."""
import html
import json
import re
import markdown


def organize_sections(abstract, sections):
    """Move complete narrative blocks under nine headings without rewriting them."""
    from collections import Counter

    parts = re.split(r'^## (.+)\n', '\n\n'.join(sections), flags=re.M)
    assert not parts[0].strip(), 'Expected sections to start with a heading'
    source = {
        title: body.strip().split('\n\n')
        for title, body in zip(parts[1::2], parts[2::2])
    }
    paper = ['## Title + Abstract\n\n' + abstract]
    moved = []

    def main(title):
        paper.append('## ' + title)

    def subsection(title, *selections):
        blocks = []
        for key, indices in selections:
            original = source[key]
            selected = original if indices is None else [original[i] for i in indices]
            blocks.extend(selected)
        moved.extend(blocks)
        paper.append('### ' + title + '\n\n' + '\n\n'.join(blocks))

    main('Introduction / Problem statement')
    subsection('Starter CSV: problem framing', ('1. Problem framing', None))
    subsection('Warehouse: the question', ('Warehouse study: data and question', [0]))

    main('Data')
    subsection('Starter CSV: data and safety', ('2. Data and safety', None))
    subsection('Warehouse: release, tables, and eligibility',
        ('Warehouse study: data and question', [1, 2, 3]),
        ('Warehouse method: predict a later window', [1]),
        ('Warehouse study: data and question', [4]),
        ('Warehouse method: predict a later window', [3]))

    main('Methodology')
    subsection('Earlier work: what changed my thinking',
        ('Earlier work: what changed my thinking', None))
    subsection('Starter CSV: baseline', ('3. Baseline', None))
    subsection('Starter CSV: methodology and model', ('4. Methodology and model', None))
    subsection('Warehouse: predict a later window',
        ('Warehouse method: predict a later window', [0, 2, 4, 5, 6, 7, 8, 9]))

    main('Results')
    subsection('Starter CSV: results and evaluation', ('5. Results and evaluation', None))
    subsection('Starter CSV: interpretation and errors', ('6. Interpretation and errors', None))
    subsection('Warehouse: selection and final check',
        ('Warehouse results: selection and final check', None))
    subsection('Warehouse: interpretation and errors',
        ('Warehouse interpretation and review guidance', [0, 1]))
    subsection('What the two datasets support', ('What the two datasets support', [0, 1]))

    main('Limitations & honest framing')
    subsection('Limitations and next checks', ('Limitations and next checks', None))
    subsection('What the two datasets cannot establish', ('What the two datasets support', [2]))

    main('Ranked recommendations')
    subsection('Starter CSV: ranked recommendations', ('7. Ranked recommendations', None))
    subsection('Warehouse: review guidance',
        ('Warehouse interpretation and review guidance', [2, 3, 4]))

    main('Reproducibility')
    subsection('Notebook, repository, and rerun instructions', ('8. Reproducibility', None))
    subsection('Warehouse: recorded choices and cached data',
        ('What the two datasets support', [3, 4]))

    main('Acknowledgments & data credit')
    blocks = source['9. Acknowledgments and data credit']
    moved.extend(blocks)
    paper.append('\n\n'.join(blocks))

    # An accidental omission, duplication, or wording edit must stop the export.
    original = [block for blocks in source.values() for block in blocks]
    assert Counter(moved) == Counter(original), 'Report content changed during reorganization'
    return '\n\n'.join(paper)

def save_paper(root, abstract, sections, receipt):
    work = root / 'work'
    title = 'Which pages should I review first for a content refresh?'
    body = '# ' + title + '\n\n**Ibrahim Irfan Nazar | Refresh / Content Opportunity Scoring**\n\n' + organize_sections(abstract, sections)
    (work/'capstone_report.md').write_text(body+'\n',encoding='utf-8')
    rendered = markdown.markdown(body, extensions=['tables', 'fenced_code', 'toc'])
    def embed(match):
        attrs = match.group(0)
        name = re.search(r'src="figures/([a-z_]+)\.svg"', attrs).group(1)
        svg = (work/'figures'/(name+'.svg')).read_text(encoding='utf-8')
        svg = svg[svg.index('<svg'):]
        # Give each embedded figure its own IDs; matplotlib reuses IDs across files.
        ids=re.findall(r'\bid="([^"]+)"',svg)
        for old in ids:
            new=name+'-'+old
            svg=svg.replace('id="'+old+'"','id="'+new+'"')
            svg=svg.replace('#'+old+'"','#'+new+'"').replace('#'+old+')','#'+new+')')
        svg = re.sub(r'<svg\b', '<svg role="img" aria-label="'+html.escape(name.replace('_',' '))+'"', svg, count=1)
        return '<figure>'+svg+'</figure>'
    rendered = re.sub(r'<img\b[^>]*src="figures/[a-z_]+\.svg"[^>]*>',embed,rendered)
    rendered = re.sub(r'<table>', '<div class="table-wrap" tabindex="0"><table>', rendered).replace('</table>','</table></div>')
    rendered = re.sub(r'<h1\b[^>]*>.*?</h1>', '', rendered, count=1, flags=re.S)
    nav = ''.join('<a href="#'+i+'">'+label+'</a>' for i,label in re.findall(r'<h2 id="([^"]+)">(.*?)</h2>',rendered))
    css = """
    :root{--ink:#142438;--blue:#1d4ed8;--line:#d8e0e9;--muted:#526479;--paper:#fff;--soft:#f2f6fc}
    *{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:1rem}
    body{margin:0;background:var(--paper);color:var(--ink);font:17px/1.7 system-ui,-apple-system,'Segoe UI',sans-serif}
    a{color:var(--blue);text-underline-offset:3px;overflow-wrap:anywhere}a:hover{text-decoration-thickness:2px}
    a:focus-visible,.table-wrap:focus-visible{outline:3px solid #087f8c;outline-offset:4px}
    .skip{position:absolute;left:1rem;top:-5rem}.skip:focus{top:1rem;background:white;padding:.5rem;z-index:5}
    header{background:#112b48;color:white;padding:4rem max(5vw,calc((100vw - 1160px)/2)) 3rem;border-bottom:8px solid #087f8c}
    .eyebrow{font-size:.82rem;letter-spacing:.13em;text-transform:uppercase;color:#afceff;margin:0 0 1rem}
    h1{font-family:Georgia,serif;font-weight:normal;font-size:clamp(2.2rem,4.4vw,3.9rem);line-height:1.12;max-width:940px;margin:0 0 1.5rem}
    header p{max-width:760px;color:#d8e9ff;margin:.4rem 0}header .finding{font-size:1.17rem;color:white}
    .layout{max-width:1230px;margin:auto;display:grid;grid-template-columns:220px minmax(0,1fr);gap:3.3rem;padding:2.8rem 2rem 5rem}
    aside{font-size:.88rem;align-self:start;position:sticky;top:1.5rem}aside strong{display:block;margin-bottom:.8rem}
    nav{max-height:calc(100vh - 6rem);overflow-y:auto;display:grid;gap:.7rem;border-left:2px solid var(--line);padding-left:1rem}nav a{color:var(--muted);text-decoration:none;line-height:1.45}
    nav a:hover{color:var(--blue)}article{min-width:0}article>p{max-width:80ch}
    h2{font:normal 2rem/1.25 Georgia,serif;margin:3.4rem 0 1.1rem;padding-top:1rem;border-top:1px solid var(--line);color:#123a65}
    h2:first-of-type{margin-top:.5rem;border:0;padding:0}h3{font-size:1.2rem}
    p{margin:.8rem 0 1rem}strong{font-weight:650}li{margin:.55rem 0}code{font:.83em/1.5 ui-monospace,Consolas,monospace;background:var(--soft);padding:.12em .3em;border-radius:3px;overflow-wrap:anywhere}
    pre{padding:1.2rem;background:#eff4fa;border-left:3px solid #087f8c;white-space:pre-wrap;overflow-wrap:anywhere}pre code{padding:0;background:none}
    .table-wrap{overflow-x:auto;margin:1.5rem 0;border:1px solid var(--line);border-radius:4px}
    table{width:100%;border-collapse:collapse;font-size:.84rem;line-height:1.55}th{background:#eaf1fb;text-align:left;white-space:normal}
    th,td{padding:.75rem .8rem;border-bottom:1px solid var(--line);vertical-align:top}tr:last-child td{border-bottom:0}tbody tr:nth-child(even){background:#f7f9fc}
    figure{margin:2rem 0 .7rem;padding:.5rem;background:white;border:1px solid var(--line)}figure svg{display:block;width:100%;height:auto}
    figure+p{font-size:.9rem;color:var(--muted)}footer{border-top:1px solid var(--line);padding:2rem;text-align:center;color:var(--muted);font-size:.85rem}
    @media(max-width:850px){.layout{grid-template-columns:1fr;padding:1.5rem;gap:1.5rem}aside{position:static}nav{max-height:none;grid-template-columns:repeat(2,minmax(0,1fr))}header{padding:2.8rem 1.5rem}h2{font-size:1.7rem;margin-top:2.4rem}}
    @media(max-width:480px){nav{grid-template-columns:1fr}.layout{padding:1.1rem}header{padding:2rem 1.1rem}body{font-size:16px}}
    @media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
    @media print{aside,.skip{display:none}.layout{display:block;padding:0}header{background:white;color:#142438;padding:1rem 0;border-bottom:2px solid #142438}header p,header .finding,.eyebrow{color:#142438}h1{font-size:28pt}body{font-size:10pt}h2{font-size:18pt}figure,tr{break-inside:avoid}.table-wrap{overflow:visible}a{color:inherit}}
    """
    hits=round(receipt['best_model_precision_at_50']*50)
    base=round(receipt['baseline_precision_at_50']*50)
    warehouse=json.loads((work/'outputs/warehouse_metrics.json').read_text(encoding='utf-8'))
    wm=warehouse['test_metrics'][warehouse['selected_model']]['precision_at_50']
    wb=warehouse['test_metrics']['momentum_rule']['precision_at_50']
    result=f'The model wins the starter comparison ({hits}/50 vs {base}/50). The momentum rule wins the warehouse forecast ({wb:.1%} vs {wm:.1%} Precision@50).'
    page=f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} | Ibrahim Irfan Nazar</title>
<meta name="description" content="A content-review study using the starter CSV and Hugging Face warehouse, with separate baselines, future-window evaluation, and clear limits.">
<style>{css}</style></head><body><a class="skip" href="#paper">Skip to the paper</a>
<header><p class="eyebrow">FlyRank ML Internship / Capstone research paper</p><h1>{html.escape(title)}</h1>
<p class="finding">{html.escape(result)}</p><p>Two datasets, separate evaluations, and one goal: useful human review.</p><p>Verified run: {receipt['run_utc'][:10]}</p></header>
<div class="layout"><aside><strong>In this paper</strong><nav aria-label="Paper sections">{nav}</nav></aside><article id="paper">{rendered}</article></div>
<footer>Local research paper | Charts and numbers generated from the capstone notebook | Built on the FlyRank ML Internship dataset</footer></body></html>"""
    path=work/'capstone_report.html'
    path.write_text(page,encoding='utf-8')
    return path
