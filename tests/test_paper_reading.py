"""The web edition uses the manuscript, including its limitations, tables and figures."""
import json
from pathlib import Path

import pytest

from zenith.paper_reading import diagram_sources, paper_reading

ROOT = Path(__file__).resolve().parents[1]
KEYS = [record['id'] for record in json.loads((ROOT / 'paper/references.json').read_text())['sources']]
DISCLOSURE = (
    'Will Cook built and directed the research infrastructure and reviewed the '
    'claims when he could. AI agents did most of the research and drafting. '
    'Cook did not independently verify every claim.'
)
FIGURES = ['fault-population', 'kept-experience-flow', 'imagined-faults', 'kept-experience-results', 'repair-loop']


def test_web_edition_preserves_citations_results_and_every_figure():
    reading = paper_reading((ROOT / 'paper/zenith.tex').read_text(), KEYS)
    assert reading['disclosure'] == '**Authorship and AI use.** ' + DISCLOSURE
    assert [s['id'] for s in reading['sections']] == ['intro', 'setting', 'conditions', 'results',
                                                      'earlier', 'related', 'research']
    blocks = [b for s in reading['sections'] for b in s['blocks']]
    markdown = '\n'.join(b['content'] for b in blocks if b['kind'] == 'markdown')
    assert all(f'](#ref-{key})' in markdown for key in KEYS)
    assert 'Hₕ,ₜ = f(ht)' in markdown
    assert '| Retained tester | 3 | 15 | 5 | 10 | 0 |' in markdown
    assert '$0.12982944' in markdown
    assert '- **Playbook v1.**' in markdown
    figures = [b for b in blocks if b['kind'] == 'figure']
    assert [f['id'] for f in figures] == FIGURES
    assert all(f['url'] == f"/assets/{f['id']}.svg" and f['alt'] and f['caption'] for f in figures)
    assert 'Held-out outcomes are withheld from repair and selection.' in figures[-1]['caption']
    assert 'failed search does not establish falsehood' in markdown


def test_every_figure_has_a_marker_and_source():
    sources = diagram_sources((ROOT / 'paper/zenith.tex').read_text())
    assert list(sources) == FIGURES
    assert all(source.startswith(r'\begin{tikzpicture}') for source in sources.values())


def test_editing_manuscript_changes_web_text_without_a_second_copy():
    tex = (ROOT / 'paper/zenith.tex').read_text()
    reading = paper_reading(tex.replace('Zenith asks whether the experience', 'A revised opening asks whether the experience'), KEYS)
    assert reading['abstract'].startswith('A revised opening asks whether the experience')
    tex = tex.replace('Retained tester & 3 & 15 & 5 & 10 & 0', 'Retained tester & 2 & 19 & 9 & 10 & 0')
    reading = paper_reading(tex, KEYS)
    assert any('| Retained tester | 2 | 19 | 9 | 10 | 0 |' in b.get('content', '')
               for s in reading['sections'] for b in s['blocks'])


def test_unsupported_tex_is_not_silently_dropped():
    tex = (ROOT / 'paper/zenith.tex').read_text().replace('Zenith asks whether', r'\unknowncommand{A result} Zenith asks whether')
    with pytest.raises(ValueError, match='Unsupported manuscript TeX'):
        paper_reading(tex, KEYS)


def test_unmarked_figure_is_rejected():
    tex = (ROOT / 'paper/zenith.tex').read_text().replace('% figure: repair-loop |', '% (marker removed)', 1)
    with pytest.raises(ValueError, match='marker'):
        diagram_sources(tex)


@pytest.mark.parametrize('replacement', ['', r'\textbf{AI tools.}'])
def test_missing_or_unrecognised_disclosure_blocks_web_publication(replacement):
    tex = (ROOT / 'paper/zenith.tex').read_text().replace(
        r'\textbf{Authorship and AI use.}', replacement)
    with pytest.raises(ValueError, match='first-page authorship and AI-use disclosure'):
        paper_reading(tex, KEYS)


def test_disclosure_edits_reach_web_without_a_second_authored_copy():
    tex = (ROOT / 'paper/zenith.tex').read_text().replace(
        'independently verify every claim.', 'independently verify every claim. A revised disclosure.')
    assert paper_reading(tex, KEYS)['disclosure'].endswith('A revised disclosure.')


@pytest.mark.parametrize('text, message', [
    ('First page\fAuthorship and AI use. ' + DISCLOSURE + '\fLast page\f', 'PDF page one'),
    ('Authorship and AI use. ' + DISCLOSURE + '\f' + 'More\f' * 9, 'page limit'),
])
def test_publication_check_rejects_displaced_disclosure_and_wrong_length(monkeypatch, text, message):
    from scripts import build_paper_reading as builder
    from zenith.web_content import PublicContent
    monkeypatch.setattr(PublicContent, 'paper', lambda self: {
        'pdf_current': True, 'reading': {'disclosure': '**Authorship and AI use.** ' + DISCLOSURE}})
    monkeypatch.setattr(builder.subprocess, 'check_output', lambda *args, **kwargs: text)
    with pytest.raises(ValueError, match=message):
        builder.check_publication()


def test_publication_check_rejects_unreviewed_pdf_pair(monkeypatch):
    from scripts import build_paper_reading as builder
    from zenith.web_content import PublicContent
    monkeypatch.setattr(PublicContent, 'paper', lambda self: {'pdf_current': False})
    with pytest.raises(ValueError, match='differ from the reviewed edition'):
        builder.check_publication()


@pytest.mark.parametrize('changed_path', ['paper/repair-loop.svg', 'paper/zenith.tex'])
def test_stale_diagram_cannot_enter_web_edition(monkeypatch, changed_path):
    from zenith import web_content
    read = web_content.safe_read
    def changed(root, path):
        data = read(root, path)
        if path == changed_path:
            return data.replace(b'Propose query', b'Revised query') if path.endswith('.tex') else data + b'\n'
        return data
    monkeypatch.setattr(web_content, 'safe_read', changed)
    with pytest.raises(ValueError, match='diagram differs'):
        web_content.PublicContent(ROOT).paper()


@pytest.mark.parametrize('extra', ['A claim that must remain visible.', r'\unsupportedfigureclaim{Important limitation}'])
def test_extra_figure_content_cannot_be_silently_dropped(extra):
    tex = (ROOT / 'paper/zenith.tex').read_text().replace(r'\end{tikzpicture}', r'\end{tikzpicture}' + '\n' + extra, 1)
    with pytest.raises(ValueError, match='Unsupported manuscript figure content'):
        paper_reading(tex, KEYS)


@pytest.mark.parametrize('math', ['$x^2$', r'\(x^2\)', r'\[x^2\]'])
def test_unknown_math_requires_explicit_projection_support(math):
    tex = (ROOT / 'paper/zenith.tex').read_text().replace('Zenith asks whether', math + ' Zenith asks whether')
    with pytest.raises(ValueError, match='Unsupported manuscript'):
        paper_reading(tex, KEYS)
