// Run-state vocabulary. Adapted from the original Zenith utils/status.ts, with
// one deliberate change: the original folded `loaded` into `success`. The
// website keeps them apart, because reused evidence is not a fresh execution.

export type NodeState = 'success' | 'loaded' | 'pending' | 'failure' | 'not_started' | 'not_reached' | 'unknown';

export function normalizeState(raw: unknown): NodeState {
  const value = String(raw ?? '').toLowerCase();
  if (value === 'success') return 'success';
  if (value === 'loaded') return 'loaded';
  if (value === 'failure' || value === 'failed' || value === 'error') return 'failure';
  if (value === 'pending' || value === 'awaiting_agent') return 'pending';
  if (value === 'not_started' || value === 'idle') return 'not_started';
  if (value === 'not_reached') return 'not_reached';
  return 'unknown';
}

export const STATE_LABEL: Record<NodeState, string> = {
  success: 'Ran',
  loaded: 'Loaded',
  pending: 'Request prepared',
  failure: 'Failed',
  not_started: 'Not started',
  not_reached: 'Not reached',
  unknown: 'No record',
};

export const STATE_DESCRIPTION: Record<NodeState, string> = {
  success: 'This step ran and its output passed the program’s required format checks. That does not establish that its explanation or prediction is correct.',
  loaded: 'Loaded from saved data. Not computed in this run.',
  pending: 'The request is prepared. No model call is recorded, so no output exists.',
  failure: 'This step was attempted but did not produce an accepted output. Read the saved error for the reason.',
  not_started: 'Never started in this run.',
  not_reached: 'The program stopped before it could attempt this step.',
  unknown: 'This run has no record for the node.',
};

// Container aggregation, adapted from aggregateContainerStatus in the original.
export function aggregateState(states: NodeState[]): NodeState | null {
  if (states.length === 0) return null;
  if (states.some((s) => s === 'failure')) return 'failure';
  if (states.every((s) => s === 'success')) return 'success';
  if (states.every((s) => s === 'loaded')) return 'loaded';
  if (states.every((s) => s === 'success' || s === 'loaded')) return 'success';
  if (states.every((s) => s === 'not_started' || s === 'not_reached')) return states[0];
  return 'unknown';
}
