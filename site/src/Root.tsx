// Chooses the page. The front page is the current study and needs no data
// request. The paper on the earlier studies keeps its reading view behind
// ?studies=earlier; links made before November 2026 (a section or reference
// anchor of that paper, or a ?node= graph link) open it too.
import { lazy, Suspense } from 'react';
import StudyPage from './components/Study';

const EarlierStudies = lazy(() => import('./App'));

const STUDY_ANCHORS = new Set(['', 'top', 'main', 'title', 'scoring', 'conditions', 'problems', 'limits', 'evidence', 'earlier']);

export function showsEarlierStudies(location: Pick<Location, 'search' | 'hash'>): boolean {
  const params = new URLSearchParams(location.search);
  if (params.get('studies') === 'earlier' || params.has('node')) return true;
  return !STUDY_ANCHORS.has(decodeURIComponent(location.hash.replace(/^#/, '')));
}

export default function Root() {
  if (!showsEarlierStudies(window.location)) return <StudyPage />;
  return (
    <Suspense fallback={<p className="page-status" role="status">Loading the earlier paper…</p>}>
      <EarlierStudies />
    </Suspense>
  );
}
