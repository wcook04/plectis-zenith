// Origin is carried by each artifact, never inferred from its visual style.
import type { Provenance } from '../api';
export const ORIGIN_LABEL: Record<string, string> = {
  authored_synthetic: 'Synthetic data', derived_synthetic_inputs: 'Computed from synthetic data',
};
export const ORIGIN_DESCRIPTION: Record<string, string> = {
  authored_synthetic: 'Invented observations of System A. No measurements from a real system are used.',
  derived_synthetic_inputs: 'Recomputed from the synthetic observations; not a separate independent source.',
};
export const PAYLOAD_LABEL: Record<string, string> = { included: 'Published in full on this site' };
export function originLabel(p?: Provenance | null): string | null {
  return p ? (ORIGIN_LABEL[p.input_origin] ?? p.input_origin.replace(/_/g, ' ')) : null;
}
