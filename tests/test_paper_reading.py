"""The web edition uses the manuscript, including its limitations and table."""
from pathlib import Path

import pytest

from zenith.paper_reading import paper_reading

ROOT = Path(__file__).resolve().parents[1]
KEYS = ['psr', 'weighted', 'ilf', 'coverup', 'voyager', 'stop', 'hyperagents']


def test_web_edition_preserves_citations_results_and_same_figure():
    reading = paper_reading((ROOT / 'paper/zenith.tex').read_text(), KEYS)
    assert [s['id'] for s in reading['sections']] == ['idea', 'results', 'next']
    blocks = [b for s in reading['sections'] for b in s['blocks']]
    markdown = '\n'.join(b['content'] for b in blocks if b['kind'] == 'markdown')
    assert all(f'](#ref-{key})' in markdown for key in KEYS)
    assert 'Hₕ,ₜ = f(ht)' in markdown
    assert '| Retained tester | 3 | 5 | 0 |' in markdown
    assert '| Fixed tester | 4 | 7 | 0 |' in markdown
    assert '$0.12982944' in markdown
    figures = [b for b in blocks if b['kind'] == 'figure']
    assert len(figures) == 1 and figures[0]['url'] == '/assets/repair-loop.svg'
    assert 'Held-out outcomes are withheld from repair.' in figures[0]['caption']
    assert 'failed search does not establish falsehood' in markdown


def test_editing_manuscript_changes_web_text_without_a_second_copy():
    tex = (ROOT / 'paper/zenith.tex').read_text()
    reading = paper_reading(tex.replace('We investigate whether retaining programs', 'A revised opening evaluates retaining programs'), KEYS)
    assert reading['abstract'].startswith('A revised opening evaluates retaining programs')
    tex = tex.replace('Retained tester & 3 & 5 & 0', 'Retained tester & 2 & 9 & 0')
    reading = paper_reading(tex, KEYS)
    assert any('| Retained tester | 2 | 9 | 0 |' in b.get('content', '')
               for s in reading['sections'] for b in s['blocks'])


def test_unsupported_tex_is_not_silently_dropped():
    tex = (ROOT / 'paper/zenith.tex').read_text().replace('We investigate whether', r'\unknowncommand{A result} We investigate whether')
    with pytest.raises(ValueError, match='Unsupported manuscript TeX'):
        paper_reading(tex, KEYS)


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
    tex = (ROOT / 'paper/zenith.tex').read_text().replace(r'\end{tikzpicture}', r'\end{tikzpicture}' + '\n' + extra)
    with pytest.raises(ValueError, match='Unsupported manuscript figure content'):
        paper_reading(tex, KEYS)


@pytest.mark.parametrize('math', ['$x^2$', r'\(x^2\)', r'\[x^2\]'])
def test_unknown_math_requires_explicit_projection_support(math):
    tex = (ROOT / 'paper/zenith.tex').read_text().replace('We investigate whether', math + ' We investigate whether')
    with pytest.raises(ValueError, match='Unsupported manuscript'):
        paper_reading(tex, KEYS)
