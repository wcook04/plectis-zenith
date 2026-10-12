// Run selector for saved local evidence. Rendered only when the backend
// reports local run access; the public site works without it.
import { useEffect, useState } from 'react';
import { api, type RunSummary } from '../api';

export type RunChoice = { kind: 'none' } | { kind: 'receipt' } | { kind: 'local'; summary: RunSummary };

type Props = {
  mission: string;
  value: string;
  onChange: (choice: RunChoice, value: string) => void;
  receiptLabel?: string;
  localEnabled: boolean;
};

const GRADE_LABEL: Record<string, string> = { red: 'has failures', green: 'no failures', amber: 'partial' };

export function RunPicker({ mission, value, onChange, receiptLabel, localEnabled }: Props) {
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!localEnabled) return;
    let live = true;
    api
      .runs({ mission, limit: 100 })
      .then((index) => live && setRuns(index.runs))
      .catch((e: Error) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [mission, localEnabled]);

  if (!localEnabled && !receiptLabel) return null;

  return (
    <label className="run-picker">
      <span className="run-picker__label">Show states from</span>
      <select
        value={value}
        onChange={(event) => {
          const next = event.target.value;
          if (next === 'none') onChange({ kind: 'none' }, next);
          else if (next === 'receipt') onChange({ kind: 'receipt' }, next);
          else {
            const summary = runs?.find((r) => r.run_id === next);
            if (summary) onChange({ kind: 'local', summary }, next);
          }
        }}
      >
        <option value="none">No run (definitions only)</option>
        {receiptLabel && <option value="receipt">{receiptLabel}</option>}
        {localEnabled && runs && (
          <optgroup label="Saved runs on this computer">
            {runs.map((run) => (
              <option key={run.run_id} value={run.run_id}>
                {run.run_id} ({run.source_kind === 'conditional_lab' ? 'conditional, ' : ''}
                {GRADE_LABEL[run.grade] ?? run.grade})
              </option>
            ))}
          </optgroup>
        )}
      </select>
      {error && <span className="inspector__warn">Saved runs unavailable: {error}</span>}
    </label>
  );
}
