import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { FamilyLockup, FamilySites, FilmSlot, ZenithMark } from '../components/Family';
import { FAMILY, clock, isReleased, siteFilms, spokenDuration, type FamilyFilm } from '../content/family';

afterEach(() => cleanup());

// Stills ship from public/ unchanged; the build copies them into dist and its
// zenith-public.json allowlist. Only the file names are read here.
const publicFiles = Object.keys(import.meta.glob('../../public/assets/films/*.webp'))
  .map(path => path.replace('../../public/', ''));

describe('family data', () => {
  it('prints and says running times', () => {
    expect(clock(295)).toBe('4:55');
    expect(clock(1800)).toBe('30:00');
    expect(clock(3723)).toBe('1:02:03');
    expect(spokenDuration(295)).toBe('4 minutes 55 seconds');
    expect(spokenDuration(327)).toBe('5 minutes 27 seconds');
    expect(spokenDuration(60)).toBe('1 minute');
    expect(spokenDuration(3661)).toBe('1 hour 1 minute 1 second');
  });

  it('lists this website and ships a still pair for every released film it shows', () => {
    expect(FAMILY.schema).toBe('will_cook_site_family_v1');
    expect(FAMILY.sites.find(site => site.id === 'zenith')?.url).toBe('https://wcook04.github.io/plectis-zenith/');
    const films = siteFilms();
    expect(films.map(film => film.id)).toEqual(['zenith']);
    for (const film of films.filter(isReleased)) {
      expect(publicFiles).toContain(`${film.still}-640.webp`);
      expect(publicFiles).toContain(`${film.still}-1280.webp`);
    }
  });
});

describe('family markup', () => {
  it('starts the header with the lockup: the plait to the home page, a rule, then the site', () => {
    const { container } = render(<header><FamilyLockup name="Zenith" href="/" mark={<ZenithMark />} /></header>);
    const [home, site] = screen.getAllByRole('link');
    expect(home).toHaveAccessibleName('Will Cook: all websites and films');
    expect(home).toHaveAttribute('href', 'https://wcook04.github.io/');
    expect(home).toHaveAttribute('rel', 'author');
    expect(home.querySelector('img')?.getAttribute('src')).toMatch(/assets\/family\/plectis\.svg$/);
    expect(home.nextElementSibling).toHaveClass('fam-lockup__rule');
    expect(home.nextElementSibling).toHaveAttribute('aria-hidden', 'true');
    expect(site).toHaveAccessibleName('Zenith');
    expect(site).toHaveAttribute('href', '/');
    expect(site.querySelector('svg.fam-mark')).toHaveAttribute('aria-hidden', 'true');
    // Nothing in the lockup loads from another host.
    expect(container.querySelector('img[src^="http"], [href^="//"]')).toBeNull();
  });

  it('renders a released film as one titled link that opens YouTube in a new tab', () => {
    const [film] = siteFilms();
    const { container } = render(<FilmSlot film={film} series="Zenith" />);
    const links = screen.getAllByRole('link');
    expect(links).toHaveLength(1);
    const title = links[0];
    expect(title).toHaveAccessibleName(/^Zenith: can an AI tester learn from the bugs it missed\?, video on YouTube, 4 minutes 55 seconds/);
    expect(title).toHaveAttribute('href', 'https://www.youtube.com/watch?v=A1Kw5hXvzVw');
    expect(title).toHaveAttribute('target', '_blank');
    expect(title).toHaveAttribute('rel', 'noopener noreferrer');
    const frame = container.querySelector('a.film-slot__frame')!;
    expect(frame).toHaveAttribute('href', title.getAttribute('href'));
    expect(frame).toHaveAttribute('aria-hidden', 'true');
    expect(frame).toHaveAttribute('tabindex', '-1');
    expect(frame).toHaveAttribute('target', '_blank');
    const still = frame.querySelector('img')!;
    expect(still).toHaveAttribute('alt', '');
    expect(still.getAttribute('src')).toBe('/assets/films/zenith-640.webp');
    expect(still.getAttribute('srcset')).toBe('/assets/films/zenith-640.webp 640w, /assets/films/zenith-1280.webp 1280w');
    expect(frame.querySelector('.film-slot__play')).not.toBeNull();
    expect(frame.querySelector('.film-slot__time')).toHaveTextContent('4:55');
    expect(screen.getByText(film.description)).toHaveClass('film-slot__text');
    expect(container.querySelector('iframe')).toBeNull();
  });

  it('holds a film without a YouTube link in preparation, with nothing to open', () => {
    const pending: FamilyFilm = { id: 'next', title: 'A working title', short: 'Working title',
      description: 'What the film will show.', youtube: null, duration_seconds: null, still: null };
    const { container } = render(<FilmSlot film={pending} series="Zenith" />);
    expect(screen.queryAllByRole('link')).toHaveLength(0);
    expect(container.querySelector('img')).toBeNull();
    expect(screen.getByText('In preparation')).toBeInTheDocument();
    expect(screen.getByText('Video in preparation')).toBeInTheDocument();
    expect(container.querySelector('.film-slot')).toHaveClass('film-slot--pending');
  });

  it('lists every website in sites.json order and marks this one as current', () => {
    render(<footer><FamilySites /></footer>);
    const nav = screen.getByRole('navigation', { name: "Will Cook's websites" });
    const links = within(nav).getAllByRole('link');
    expect(links.map(link => link.textContent)).toEqual([...FAMILY.sites.map(site => site.short), 'All websites and films']);
    expect(links.map(link => link.getAttribute('href'))).toEqual([...FAMILY.sites.map(site => site.url), 'https://wcook04.github.io/']);
    expect(links.filter(link => link.getAttribute('aria-current') === 'page').map(link => link.textContent)).toEqual(['Zenith']);
  });
});
