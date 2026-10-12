// Mixed-data edition: which inputs are real, synthetic or derived. Read from
// each node's demo_provenance; nothing here decides it.
import type { Provenance } from '../api';

export const ORIGIN_LABEL: Record<string, string> = {
  real_saved_input: 'Real input',
  authored_synthetic: 'Synthetic',
  derived_mixed_inputs: 'Derived',
};

export const ORIGIN_DESCRIPTION: Record<string, string> = {
  real_saved_input: 'A real saved market artifact, copied byte for byte into the computation.',
  authored_synthetic: 'Invented examples written for this demonstration. Not an anonymised historical observation.',
  derived_mixed_inputs: 'Recomputed by the existing calculator from the mixed inputs.',
};

export const PAYLOAD_LABEL: Record<string, string> = {
  included: 'Published in full on this site',
  withheld_pending_permissions_review: 'Withheld from the public site while data permissions are reviewed',
  withheld_pending_upstream_permissions_review: 'Withheld while the permissions of its real inputs are reviewed',
};

export function originLabel(p?: Provenance | null): string | null {
  if (!p) return null;
  return ORIGIN_LABEL[p.input_origin] ?? p.input_origin.replace(/_/g, ' ');
}
