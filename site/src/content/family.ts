// Will Cook's websites share a header ladder, film slots and a footer list of
// sister sites (wcook04.github.io, docs/family.md). family.json is an unchanged
// copy of that repository's sites.json; replace it, never edit it here.
import family from './family.json';

export type FamilySite = {
  id: string;
  name: string;
  short: string;
  url: string;
  films: string[];
};

export type FamilyFilm = {
  id: string;
  title: string;
  short: string;
  description: string;
  youtube: string | null;
  duration_seconds: number | null;
  still: string | null;
};

export type Family = {
  schema: string;
  owner: { name: string; home: string };
  sites: FamilySite[];
  films: FamilyFilm[];
};

export const FAMILY = family as unknown as Family;

/** This website's entry in family.json. */
export const SITE_ID = 'zenith';

export function siteFilms(siteId = SITE_ID): FamilyFilm[] {
  const site = FAMILY.sites.find(entry => entry.id === siteId);
  return (site?.films ?? []).map(id => FAMILY.films.find(film => film.id === id))
    .filter((film): film is FamilyFilm => Boolean(film));
}

/** A released film has a YouTube link, a running time and a still. */
export function isReleased(film: FamilyFilm): film is FamilyFilm & { youtube: string; duration_seconds: number; still: string } {
  return Boolean(film.youtube) && typeof film.duration_seconds === 'number' && Boolean(film.still);
}

/** The running time printed on the still: 4:55, or 1:02:03 past an hour. */
export function clock(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  const pad = (value: number) => String(value).padStart(2, '0');
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
}

/** The running time in words, for the title link's accessible name. */
export function spokenDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  const unit = (value: number, name: string) => `${value} ${name}${value === 1 ? '' : 's'}`;
  return [h && unit(h, 'hour'), m && unit(m, 'minute'), s && unit(s, 'second')]
    .filter(Boolean).join(' ') || unit(0, 'second');
}
