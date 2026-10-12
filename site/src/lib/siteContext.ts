import { createContext, useContext } from 'react';

// Site-wide facts components need without prop drilling: the evidence routes
// the backend currently lists (they differ between data editions).
export const SiteEvidenceContext = createContext<Record<string, string>>({});
export const useSiteEvidence = () => useContext(SiteEvidenceContext);
