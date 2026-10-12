// Readable structured view for recorded payloads, with a raw JSON toggle.
// Everything renders as text; model output is data, never markup.
import { useState } from 'react';
import { CopyButton } from './CopyButton';

const PREVIEW_ITEMS = 12;

function Value({ value, depth }: { value: unknown; depth: number }) {
  if (value === null) return <span className="jv-null">null</span>;
  if (typeof value === 'string') {
    return value.length > 220 || value.includes('\n') ? (
      <span className="jv-longtext">{value}</span>
    ) : (
      <span className="jv-string">{value}</span>
    );
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return <span className="jv-scalar">{String(value)}</span>;
  }
  if (Array.isArray(value)) return <ArrayView items={value} depth={depth} />;
  if (isTable(value)) return <TableView value={value} depth={depth} />;
  if (typeof value === 'object') return <ObjectView value={value as Record<string, unknown>} depth={depth} />;
  return <span>{String(value)}</span>;
}

type Table = { columns: string[]; rows: unknown[][] } & Record<string, unknown>;

// Feed artifacts store tables as { columns, rows }; show them as tables.
function isTable(value: unknown): value is Table {
  if (!value || typeof value !== 'object') return false;
  const v = value as Record<string, unknown>;
  return Array.isArray(v.columns) && Array.isArray(v.rows) && v.rows.every((r) => Array.isArray(r));
}

function TableView({ value, depth }: { value: Table; depth: number }) {
  const [all, setAll] = useState(false);
  const rows = all ? value.rows : value.rows.slice(0, 25);
  const rest = Object.fromEntries(Object.entries(value).filter(([k]) => k !== 'columns' && k !== 'rows'));
  return (
    <div className="jv-table-wrap">
      <table className="jv-table">
        <thead>
          <tr>
            {value.columns.map((c) => (
              <th key={String(c)} scope="col">
                {String(c)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j} className={typeof cell === 'number' ? 'is-num' : undefined}>
                  {cell === null ? '' : typeof cell === 'object' ? JSON.stringify(cell) : String(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {value.rows.length > 25 && (
        <button type="button" className="z-link-button" onClick={() => setAll(!all)}>
          {all ? 'Show fewer rows' : `Show all ${value.rows.length} rows`}
        </button>
      )}
      {Object.keys(rest).length > 0 && <ObjectView value={rest} depth={depth + 1} />}
    </div>
  );
}

function ArrayView({ items, depth }: { items: unknown[]; depth: number }) {
  const [all, setAll] = useState(false);
  if (items.length === 0) return <span className="jv-null">empty list</span>;
  const shown = all ? items : items.slice(0, PREVIEW_ITEMS);
  return (
    <div className="jv-list">
      <ol>
        {shown.map((item, index) => (
          <li key={index}>
            <Value value={item} depth={depth + 1} />
          </li>
        ))}
      </ol>
      {items.length > PREVIEW_ITEMS && (
        <button type="button" className="z-link-button" onClick={() => setAll(!all)}>
          {all ? 'Show fewer' : `Show all ${items.length} items`}
        </button>
      )}
    </div>
  );
}

function ObjectView({ value, depth }: { value: Record<string, unknown>; depth: number }) {
  const entries = Object.entries(value);
  if (entries.length === 0) return <span className="jv-null">empty record</span>;
  return (
    <dl className="jv-object">
      {entries.map(([key, child]) => {
        const nested = child !== null && typeof child === 'object';
        const size = Array.isArray(child) ? child.length : nested ? Object.keys(child as object).length : 0;
        return nested && depth >= 1 ? (
          <details key={key} className="jv-entry" open={depth < 2 && size <= 6}>
            <summary>
              <span className="jv-key">{key}</span>
              <span className="jv-size">{Array.isArray(child) ? `${size} items` : `${size} fields`}</span>
            </summary>
            <Value value={child} depth={depth + 1} />
          </details>
        ) : (
          <div key={key} className="jv-entry">
            <dt className="jv-key">{key}</dt>
            <dd>
              <Value value={child} depth={depth + 1} />
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

export function tryParseJson(text: string): unknown | undefined {
  const trimmed = text.trim();
  if (!trimmed.startsWith('{') && !trimmed.startsWith('[')) return undefined;
  try {
    return JSON.parse(trimmed);
  } catch {
    return undefined;
  }
}

export function JsonView({ value, label }: { value: unknown; label: string }) {
  const [raw, setRaw] = useState(false);
  const rawText = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  const structured = typeof value === 'string' ? tryParseJson(value) : value;
  const canStructure = structured !== undefined && typeof structured === 'object' && structured !== null;
  return (
    <div className="jv">
      <div className="jv-bar">
        <span className="jv-label">{label}</span>
        {canStructure && (
          <button type="button" className="z-chip-button" aria-pressed={raw} onClick={() => setRaw(!raw)}>
            {raw ? 'Readable view' : 'Raw JSON'}
          </button>
        )}
        <CopyButton text={rawText} label="Copy" />
      </div>
      {canStructure && !raw ? (
        <div className="jv-body">
          <Value value={structured} depth={0} />
        </div>
      ) : (
        <pre className="z-pre">{rawText}</pre>
      )}
    </div>
  );
}
