// The parts every one of Will Cook's websites shares, with the markup of
// wcook04.github.io docs/family.md and the unchanged styles/family.css.
import type { ReactNode } from 'react';
import { FAMILY, SITE_ID, clock, isReleased, spokenDuration, type FamilyFilm } from '../content/family';

/**
 * The start of the header: the Plectis plait opens the home page (every
 * website and film), a short upright rule, then this site's mark and name
 * open this site's front page. The plait is public/assets/family/plectis.svg,
 * a copy of wcook04.github.io assets/family/marks/plectis.svg, which keeps its
 * own day and night palettes; the site mark is inline SVG in the site's inks.
 */
export function FamilyLockup({ name, href, mark }: { name: string; href: string; mark: ReactNode }) {
  return (
    <span className="fam-lockup">
      <a className="fam-lockup__home" href={FAMILY.owner.home} rel="author"
        title={`All of ${FAMILY.owner.name}'s projects and videos`}>
        <img src={`${import.meta.env.BASE_URL}assets/family/plectis.svg`}
          alt={`${FAMILY.owner.name}: all projects and videos`} width={26} height={26} />
      </a>
      <span className="fam-lockup__rule" aria-hidden="true"></span>
      <a className="fam-lockup__site" href={href}>
        {mark}
        <span className="fam-lockup__name" translate="no">{name}</span>
      </a>
    </span>
  );
}

/** Zenith's mark: the sun at its highest point on its arc (assets/family/marks/zenith.svg). */
export function ZenithMark() {
  return (
    <svg className="fam-mark" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path className="fam-mark__cool" d="M3.5 19a8.5 8.5 0 0 1 17 0" />
      <path className="fam-mark__ink" d="M1.5 19h21" />
      <circle className="fam-mark__warm-fill" cx="12" cy="10.5" r="3.2" />
    </svg>
  );
}

/**
 * A film's place on a page. The still and the title open the same YouTube
 * page in a new tab, so only the title is in the Tab order, and its name says
 * the running time in words. A film without a YouTube link is held in
 * preparation and links nowhere. Stills are served from public/<still>-640.webp
 * and -1280.webp under the build's base path.
 */
export function FilmSlot({ film, series, size, sizes = '(min-width: 960px) 480px, 100vw' }: {
  film: FamilyFilm;
  series: string;
  size?: 'small' | 'large';
  sizes?: string;
}) {
  const variant = size ? ` film-slot--${size}` : '';
  if (!isReleased(film)) {
    return (
      <figure className={`film-slot film-slot--pending${variant}`}>
        <div className="film-slot__frame film-slot__frame--pending" aria-hidden="true">
          <span className="film-slot__series">{series}</span>
          <span className="film-slot__name">{film.short}</span>
          <span className="film-slot__status">In preparation</span>
        </div>
        <figcaption className="film-slot__caption">
          <p className="film-slot__title">{film.title}</p>
          <p className="film-slot__meta">Video in preparation</p>
          <p className="film-slot__text">{film.description}</p>
        </figcaption>
      </figure>
    );
  }
  const still = `${import.meta.env.BASE_URL}${film.still}`;
  return (
    <figure className={`film-slot${variant}`}>
      <a className="film-slot__frame" href={film.youtube} target="_blank"
        rel="noopener noreferrer" aria-hidden="true" tabIndex={-1}>
        <img src={`${still}-640.webp`}
          srcSet={`${still}-640.webp 640w, ${still}-1280.webp 1280w`}
          sizes={sizes}
          alt="" width={1280} height={720} loading="lazy" decoding="async" />
        <span className="film-slot__play"></span>
        <span className="film-slot__time">{clock(film.duration_seconds)}</span>
      </a>
      <figcaption className="film-slot__caption">
        <p className="film-slot__title"><a href={film.youtube} target="_blank"
          rel="noopener noreferrer">{film.title}<span
          className="sr-only">, video on YouTube, {spokenDuration(film.duration_seconds)}</span></a></p>
        <p className="film-slot__text">{film.description}</p>
      </figcaption>
    </figure>
  );
}

/** The footer's list of every website, in sites.json order, this one marked. */
export function FamilySites({ current = SITE_ID }: { current?: string }) {
  return (
    <nav className="fam-sites" aria-label="Will Cook's websites">
      <p className="fam-sites__title">More from Will Cook</p>
      <ul className="fam-sites__list">
        {FAMILY.sites.map(site => (
          <li key={site.id}>
            <a href={site.url} aria-current={site.id === current ? 'page' : undefined}>{site.short}</a>
          </li>
        ))}
        <li><a href={FAMILY.owner.home}>All projects and videos</a></li>
      </ul>
    </nav>
  );
}
