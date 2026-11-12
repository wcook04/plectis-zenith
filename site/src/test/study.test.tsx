import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import StudyPage from '../components/Study';
import { showsEarlierStudies } from '../Root';
import study from '../content/keptExperience.json';

const REPORT = 'https://github.com/wcook04/plectis-zenith/blob/2b325e2de0fb763d0998f2a4f61fac59001ded59/docs/studies/kept-experience/README.md';

beforeEach(() => {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false, media: query, addEventListener: vi.fn(), removeEventListener: vi.fn(),
  })) as unknown as typeof window.matchMedia;
});
afterEach(() => cleanup());

const pageText = () => (document.body.textContent ?? '').replace(/\s+/g, ' ');

describe('study page', () => {
  it('leads with the question, both videos and the study report', () => {
    render(<StudyPage />);
    const headings = screen.getAllByRole('heading', { level: 1 });
    expect(headings).toHaveLength(1);
    expect(headings[0]).toHaveTextContent('Does a record of missed bugs help an AI tester on new programs?');

    const short = screen.getByRole('link', { name: /1 minute 54 seconds/ });
    expect(short).toHaveAttribute('href', 'https://www.youtube.com/watch?v=SIqD9PTFR7g');
    const full = screen.getByRole('link', { name: /5 minutes 3 seconds/ });
    expect(full).toHaveAttribute('href', 'https://www.youtube.com/watch?v=wUxp2Wohmq0');
    for (const link of [short, full]) {
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    }

    const report = screen.getByRole('link', { name: 'Read the study report' });
    expect(report.getAttribute('href')).toBe(REPORT);
    expect(report).toHaveAttribute('target', '_blank');
  });

  it('prints the headline figures', () => {
    render(<StudyPage />);
    const text = pageText();
    for (const figure of ['69.2%', '77.0%', '+7.9 points', '+1.4 to +14.7',
      '58 held-out problems with 277 fault classes', 'Better on 20 problems, worse on 6, equal on 32']) {
      expect(text).toContain(figure);
    }
  });

  it('prints every condition as the study report tabulates it, with a real minus sign', () => {
    render(<StudyPage />);
    const table = screen.getByRole('region', { name: 'Results for all eight conditions' });
    // Label, exposed, change, 95% interval, better and worse: the table in docs/studies/kept-experience/README.md at 2b325e2.
    const expected: [RegExp, string, string, string, string][] = [
      [/^Generic testing advice$/, '65.8%', '−3.4', '−9.6 to +2.6', '14, 16'],
      [/^Practice record$/, '77.0%', '+7.9', '+1.4 to +14.7', '20, 6'],
      [/^Rules v1/, '68.4%', '−0.8', '−7.3 to +5.8', '15, 14'],
      [/^Rules v2/, '72.7%', '+3.5', '−3.2 to +10.7', '14, 11'],
      [/^Imagined faults$/, '68.3%', '−0.9', '−7.4 to +5.8', '14, 17'],
      [/^Imagined faults and the record$/, '72.7%', '+3.6', '−2.8 to +10.1', '17, 15'],
      [/random/i, '42.8%', '−26.4', '−35.0 to −17.6', '12, 45'],
    ];
    for (const [label, exposed, change, interval, betterWorse] of expected) {
      const row = within(table).getByRole('rowheader', { name: label }).closest('tr')!;
      const cells = within(row).getAllByRole('cell');
      expect(cells[0]).toHaveTextContent(exposed);
      expect(cells[1].textContent).toBe(change);
      expect(cells[2]).toHaveTextContent(interval);
      // The page prints better, equal, worse; equal is the rest of the 58 problems.
      const [better, worse] = betterWorse.split(', ').map(Number);
      expect(cells[3].textContent).toBe(`${better}, ${58 - better - worse}, ${worse}`);
    }
    const nothing = within(table).getByRole('rowheader', { name: 'Nothing' }).closest('tr')!;
    expect(within(nothing).getAllByRole('cell')[0]).toHaveTextContent('69.2%');
    expect(table.textContent).toContain('−');
    expect(table.textContent).not.toMatch(/-\d/);
  });

  it('lets the keyboard move between the 58 problems', () => {
    render(<StudyPage />);
    const group = screen.getByRole('group', { name: 'Change in score for each held-out problem' });
    const buttons = within(group).getAllByRole('button');
    expect(buttons).toHaveLength(58);
    expect(buttons.filter(button => button.getAttribute('tabindex') === '0')).toHaveLength(1);
    const start = buttons.findIndex(button => button.getAttribute('aria-pressed') === 'true');
    expect(start).toBeGreaterThanOrEqual(0);
    expect(start).toBeLessThan(buttons.length - 1);
    expect(buttons[start]).toHaveAttribute('tabindex', '0');
    fireEvent.keyDown(buttons[start], { key: 'ArrowRight' });
    const after = within(group).getAllByRole('button');
    expect(after[start]).toHaveAttribute('aria-pressed', 'false');
    expect(after[start + 1]).toHaveAttribute('aria-pressed', 'true');
    expect(after[start + 1]).toHaveAttribute('tabindex', '0');
    expect(after.filter(button => button.getAttribute('tabindex') === '0')).toHaveLength(1);
    expect(document.activeElement).toBe(after[start + 1]);
  });

  it('keeps out wording the study does not support', () => {
    render(<StudyPage />);
    const text = pageText();
    for (const phrase of ['77% of 535', 'of 535', 'half the gain is timeouts', 'beats rules', 'every bug', '—']) {
      expect(text).not.toContain(phrase);
    }
    expect(text).not.toMatch(/\bwe\b/i);
  });
});

describe('study data', () => {
  it('reproduces the headline from the 58 problems', () => {
    const { problems } = study;
    expect(problems).toHaveLength(58);
    const mean = (values: number[]) => values.reduce((sum, value) => sum + value, 0) / values.length;
    const round4 = (value: number) => Math.round(value * 1e4) / 1e4;
    expect(round4(mean(problems.map(problem => problem.none)))).toBe(0.6917);
    expect(round4(mean(problems.map(problem => problem.record)))).toBe(0.7702);
    const changes = problems.map(problem => problem.record - problem.none);
    expect(changes.filter(change => change > 1e-9)).toHaveLength(20);
    expect(changes.filter(change => change < -1e-9)).toHaveLength(6);
    expect(changes.filter(change => Math.abs(change) <= 1e-9)).toHaveLength(32);
    expect(problems.reduce((sum, problem) => sum + problem.faults, 0)).toBe(277);
    expect(study.held_out).toMatchObject({ problems: 58, fault_classes: 277 });
  });
});

describe('page choice', () => {
  const at = (search: string, hash: string) => showsEarlierStudies({ search, hash });

  it('opens the study for its own anchors', () => {
    expect(at('', '')).toBe(false);
    expect(at('', '#limits')).toBe(false);
    expect(at('', '#top')).toBe(false);
  });

  it('opens the earlier paper for its route, graph links and old anchors', () => {
    expect(at('?studies=earlier', '')).toBe(true);
    expect(at('?node=x', '')).toBe(true);
    expect(at('', '#paper')).toBe(true);
    expect(at('', '#results')).toBe(true);
    expect(at('', '#ref-3')).toBe(true);
  });
});
