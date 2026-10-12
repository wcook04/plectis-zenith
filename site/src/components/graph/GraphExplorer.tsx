// Interactive native-graph explorer: a readable overview first, expandable
// groups, a selected-node neighbourhood, and an inspector beside the canvas.
// The interaction grammar (wave columns, lane rows, containers that expand,
// four-tier emphasis, hiding implied skip links, fit and zoom controls) comes
// from the original Zenith GraphViewer; here it reads only the website API.
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import ReactFlow, {
  MarkerType,
  ReactFlowProvider,
  useNodesInitialized,
  useReactFlow,
  type Edge,
  type Node,
} from 'reactflow';
import 'reactflow/dist/style.css';
import type { Graph } from '../../api';
import { laneColor, laneLabel, LANE_ORDER } from '../../lib/lanes';
import { CHECKPOINTS, nodeFamily, nodeName, nodeRole } from '../../lib/naming';
import { aggregateState, normalizeState, STATE_LABEL, type NodeState } from '../../lib/status';
import { useMediaQuery, usePrefersReducedMotion } from '../../lib/hooks';
import { Inspector, type RunContext } from '../Inspector';
import { NODE_TYPES, type Emphasis } from './GraphNodes';
import { layoutGraph, neighbourhood, NODE_H, NODE_W } from './layout';
import { EDGE_TYPES } from './SkipEdge';

export type ExplorerProps = {
  graph: Graph;
  title: string;
  initialExpanded?: string[];
  initialSelected?: string | null;
  run?: RunContext | null;
  runControl?: React.ReactNode;
  onSelectionChange?: (id: string | null) => void;
  maxHeight?: number;
};

export function GraphExplorer(props: ExplorerProps) {
  const narrow = useMediaQuery('(max-width: 760px)');
  return narrow ? (
    <StagedExplorer {...props} />
  ) : (
    <ReactFlowProvider>
      <CanvasExplorer {...props} />
    </ReactFlowProvider>
  );
}

function useRunStates(graph: Graph, run: RunContext | null | undefined): Record<string, NodeState> | null {
  return useMemo(() => {
    if (!run) return null;
    const raw = run.kind === 'local' ? run.summary.node_outcomes : run.states;
    const states: Record<string, NodeState> = {};
    graph.nodes.forEach((node) => {
      states[node.id] = normalizeState(raw[node.id]);
    });
    return states;
  }, [graph, run]);
}

function useSelection(props: ExplorerProps, families: Map<string, { members: string[] }>) {
  const { graph, initialSelected, onSelectionChange } = props;
  const [selected, setSelected] = useState<string | null>(
    initialSelected && graph.nodes.some((n) => n.id === initialSelected) ? initialSelected : null,
  );
  const [expanded, setExpanded] = useState<Set<string>>(() => {
    const start = new Set(props.initialExpanded ?? []);
    if (selected) families.forEach((entry, key) => entry.members.includes(selected) && start.add(key));
    return start;
  });
  const select = useCallback(
    (id: string | null) => {
      setSelected(id);
      if (id) {
        families.forEach((entry, key) => {
          if (entry.members.includes(id)) setExpanded((prev) => (prev.has(key) ? prev : new Set(prev).add(key)));
        });
      }
      onSelectionChange?.(id);
    },
    [families, onSelectionChange],
  );
  return { selected, select, expanded, setExpanded };
}

// SVG marker colours cannot read CSS variables, so resolve the theme's
// colours and re-resolve when the theme changes.
function useResolvedColours() {
  const read = useCallback(() => {
    const style = getComputedStyle(document.documentElement);
    const lanes: Record<string, string> = {};
    LANE_ORDER.forEach((lane) => {
      lanes[lane] = style.getPropertyValue(lane === 'SPINE' ? '--ink' : `--lane-${lane.toLowerCase()}`).trim() || '#888';
    });
    return { lanes, edge: style.getPropertyValue('--edge').trim() || '#888', ink: style.getPropertyValue('--ink').trim() || '#222' };
  }, []);
  const [colours, setColours] = useState(read);
  useEffect(() => {
    const update = () => setColours(read());
    const observer = new MutationObserver(update);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    const media = window.matchMedia?.('(prefers-color-scheme: dark)');
    media?.addEventListener('change', update);
    return () => {
      observer.disconnect();
      media?.removeEventListener('change', update);
    };
  }, [read]);
  return colours;
}

const PAD = 28;
const LEGEND_SPACE = 8;

function CanvasExplorer(props: ExplorerProps) {
  const { graph, title, run, runControl, maxHeight = 720 } = props;
  const families = useMemo(() => layoutGraph(graph, new Set()).families, [graph]);
  const { selected, select, expanded, setExpanded } = useSelection(props, families);
  const [lineageOnly, setLineageOnly] = useState(false);
  const [allDeps, setAllDeps] = useState(false);
  const reduced = usePrefersReducedMotion();
  const flow = useReactFlow();
  const stageRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLDivElement>(null);
  const lastAction = useRef<{ kind: 'expand'; key: string } | { kind: 'fit' }>({ kind: 'fit' });
  const states = useRunStates(graph, run);
  const colours = useResolvedColours();

  const layout = useMemo(() => layoutGraph(graph, expanded), [graph, expanded]);
  const lineage = useMemo(() => (selected ? neighbourhood(graph, selected) : null), [graph, selected]);

  // Size the canvas to the drawing: the overview reads near full size and no
  // dead band of empty canvas sits under it.
  const [stageWidth, setStageWidth] = useState(1100);
  useLayoutEffect(() => {
    const el = stageRef.current;
    if (!el) return;
    const observer = new ResizeObserver(() => setStageWidth(el.clientWidth));
    observer.observe(el);
    setStageWidth(el.clientWidth);
    return () => observer.disconnect();
  }, []);
  const bounds = useMemo(() => {
    const boxes = [...layout.items, ...layout.frames];
    const minX = Math.min(...boxes.map((b) => b.x));
    const maxX = Math.max(...boxes.map((b) => b.x + b.w));
    const minY = Math.min(0, ...boxes.map((b) => b.y));
    const maxY = Math.max(...boxes.map((b) => b.y + b.h));
    return { w: maxX - minX, h: maxY - minY };
  }, [layout]);
  const height = useMemo(() => {
    const zoom = Math.min(1, (stageWidth - PAD * 2) / bounds.w);
    return Math.round(Math.max(300, Math.min(maxHeight, bounds.h * zoom + PAD * 2 + LEGEND_SPACE)));
  }, [stageWidth, bounds, maxHeight]);

  const toggleFamily = useCallback(
    (key: string) => {
      setExpanded((prev) => {
        const next = new Set(prev);
        if (next.has(key)) {
          next.delete(key);
          lastAction.current = { kind: 'fit' };
        } else {
          next.add(key);
          lastAction.current = { kind: 'expand', key };
        }
        return next;
      });
    },
    [setExpanded],
  );

  const { nodes, edges } = useMemo(() => {
    const role = new Map<string, Emphasis>();
    if (selected && lineage) {
      const tag = (ids: Set<string>, emphasis: Emphasis) =>
        ids.forEach((id) => {
          const renderId = layout.renderIdOf.get(id);
          if (renderId && !role.has(renderId)) role.set(renderId, emphasis);
        });
      const self = layout.renderIdOf.get(selected);
      if (self) role.set(self, 'selected');
      tag(lineage.inputs, 'input');
      tag(lineage.consumers, 'consumer');
      tag(lineage.ancestors, 'ancestor');
      tag(lineage.descendants, 'descendant');
    }
    const emphasisOf = (id: string): Emphasis => (selected ? (role.get(id) ?? 'background') : undefined);
    const filtering = lineageOnly && selected !== null;
    const hide = (id: string) => filtering && !role.has(id);

    const rfNodes: Node[] = [];
    layout.bands.forEach((band) => {
      rfNodes.push({
        id: band.id,
        type: 'zband',
        position: { x: 0, y: band.y },
        style: { width: 900, height: 40 },
        data: { title: band.title, detail: band.detail },
        selectable: false,
        draggable: false,
        focusable: false,
        hidden: filtering,
      });
    });
    layout.frames.forEach((frame) => {
      rfNodes.push({
        id: frame.id,
        type: 'zframe',
        position: { x: frame.x, y: frame.y },
        style: { width: frame.w, height: frame.h },
        data: { family: frame.family, count: frame.members.length, onCollapse: toggleFamily },
        selectable: false,
        draggable: false,
        focusable: false,
        zIndex: -1,
        hidden: filtering,
      });
    });
    layout.items.forEach((item) => {
      const common = {
        id: item.id,
        position: { x: item.x, y: item.y },
        style: { width: item.w, height: item.h },
        draggable: false,
        focusable: false,
        hidden: hide(item.id),
      };
      if (item.kind === 'node') {
        rfNodes.push({
          ...common,
          type: 'znode',
          data: {
            node: item.node,
            mission: graph.mission,
            state: states ? states[item.id] : null,
            emphasis: emphasisOf(item.id),
            onSelect: select,
          },
        });
      } else {
        rfNodes.push({
          ...common,
          type: 'zgroup',
          data: {
            family: item.family,
            members: item.members,
            lanes: item.lanes,
            state: states ? aggregateState(item.members.map((m) => states[m.id])) : null,
            emphasis: emphasisOf(item.id),
            onExpand: toggleFamily,
          },
        });
      }
    });

    const selfId = selected ? layout.renderIdOf.get(selected) : undefined;
    const rfEdges: Edge[] = [];
    const itemById = new Map(layout.items.map((item) => [item.id, item]));
    let stackSlot = 0;
    layout.edges.forEach((edge) => {
      const from = itemById.get(edge.source);
      const to = itemById.get(edge.target);
      const stacked = from !== undefined && to !== undefined && from.column === to.column;
      const direct = selfId !== undefined && (edge.source === selfId || edge.target === selfId);
      if (edge.redundant && !allDeps && !direct) return;
      const sourceRole = role.get(edge.source);
      const targetRole = role.get(edge.target);
      const inLineage =
        selfId !== undefined &&
        sourceRole !== undefined &&
        targetRole !== undefined &&
        sourceRole !== 'background' &&
        targetRole !== 'background' &&
        // an ancestor chain or a descendant chain, never across them
        !((sourceRole === 'descendant' || sourceRole === 'consumer') && (targetRole === 'ancestor' || targetRole === 'input'));
      if (filtering && !inLineage && !direct) return;
      const tone = !selfId ? 'rest' : direct ? 'direct' : inLineage ? 'lineage' : 'dim';
      const stroke = direct ? (edge.target === selfId ? colours.lanes[edge.lane] ?? colours.ink : colours.ink) : colours.edge;
      rfEdges.push({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        type: stacked ? 'stack' : edge.routed ? 'routed' : 'smoothstep',
        pathOptions: { borderRadius: 10 },
        data: stacked
          ? { width: from!.w, slot: stackSlot++ }
          : edge.routed
            ? { channelY: edge.channelY, slot: edge.slot }
            : undefined,
        className: `z-edge z-edge--${tone}${edge.skip ? ' z-edge--skip' : ''}`,
        style: { stroke },
        markerEnd: { type: MarkerType.ArrowClosed, width: 13, height: 13, color: stroke },
        focusable: false,
        zIndex: direct ? 1 : 0,
      } as Edge);
    });
    return { nodes: rfNodes, edges: rfEdges };
  }, [layout, graph.mission, selected, lineage, lineageOnly, allDeps, states, select, toggleFamily, colours]);

  // Fit once nodes are measured and when the structure changes; a single
  // expanded group is framed at reading size instead of shrinking everything.
  const initialised = useNodesInitialized();
  const fitted = useRef(false);
  const structureKey = `${graph.mission}|${Array.from(expanded).sort().join(',')}|${lineageOnly ? selected : ''}|${height}`;
  // The stage grows while the inspector is open so instructions stay readable;
  // that change does not refit the drawing.
  const stageHeight = selected ? Math.max(height, 660) : height;
  useEffect(() => {
    if (!initialised) return;
    const first = !fitted.current;
    fitted.current = true;
    const duration = reduced || first ? 0 : 280;
    const frame = window.requestAnimationFrame(() => {
      const action = lastAction.current;
      lastAction.current = { kind: 'fit' };
      if (first && selected && !lineageOnly) {
        // Opened with a node already selected (deep link or a run switch):
        // frame its neighbourhood at reading size beside the inspector.
        const ids = new Set<string>();
        [selected, ...(lineage ? [...lineage.inputs, ...lineage.consumers] : [])].forEach((id) => {
          const renderId = layout.renderIdOf.get(id);
          if (renderId) ids.add(renderId);
        });
        flow.fitView({ nodes: [...ids].map((id) => ({ id })), padding: 0.16, maxZoom: 0.9, duration: 0 });
      } else if (action.kind === 'expand' && !lineageOnly) {
        const members = layout.families.get(action.key)?.members ?? [];
        flow.fitView({ nodes: [...members.map((id) => ({ id })), { id: `frame:${action.key}` }], padding: 0.18, maxZoom: 0.95, duration });
      } else {
        flow.fitView({ padding: 0.06, maxZoom: 1, duration });
      }
    });
    return () => window.cancelAnimationFrame(frame);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [structureKey, initialised, flow, reduced, layout, lineageOnly]);

  // Opening the inspector narrows the canvas; keep the selected node in view.
  useEffect(() => {
    if (!selected) return;
    const frame = window.requestAnimationFrame(() => {
      const renderId = layout.renderIdOf.get(selected);
      const item = layout.items.find((i) => i.id === renderId);
      const canvas = canvasRef.current;
      if (!item || !canvas) return;
      const { x, y, zoom } = flow.getViewport();
      const left = item.x * zoom + x;
      const right = (item.x + item.w) * zoom + x;
      const top = item.y * zoom + y;
      const bottom = (item.y + item.h) * zoom + y;
      if (left < 12 || right > canvas.clientWidth - 12 || top < 12 || bottom > canvas.clientHeight - 12) {
        flow.setCenter(item.x + item.w / 2, item.y + item.h / 2, { zoom, duration: reduced ? 0 : 260 });
      }
    });
    return () => window.cancelAnimationFrame(frame);
  }, [selected, layout, flow, reduced]);

  const centerOn = useCallback(
    (id: string) => {
      window.requestAnimationFrame(() =>
        window.requestAnimationFrame(() => {
          const renderId = layout.renderIdOf.get(id);
          const item = layout.items.find((i) => i.id === renderId);
          if (!item) return;
          const zoom = Math.max(flow.getZoom(), 0.8);
          flow.setCenter(item.x + NODE_W / 2, item.y + NODE_H / 2, { zoom, duration: reduced ? 0 : 280 });
        }),
      );
    },
    [flow, layout, reduced],
  );

  const navigate = useCallback(
    (id: string) => {
      select(id);
      centerOn(id);
    },
    [select, centerOn],
  );

  const allExpanded = layout.families.size > 0 && Array.from(layout.families.keys()).every((k) => expanded.has(k));

  return (
    <div className={`explorer${selected ? ' has-inspector' : ''}`}>
      <div className="explorer__bar">
        <NodeSearch graph={graph} onPick={navigate} />
        <div className="explorer__actions">
          <button
            type="button"
            className="z-chip-button"
            onClick={() => {
              lastAction.current = { kind: 'fit' };
              setExpanded(allExpanded ? new Set() : new Set(layout.families.keys()));
            }}
          >
            {allExpanded ? 'Collapse groups' : 'Show every node'}
          </button>
          <button type="button" className="z-chip-button" aria-pressed={allDeps} onClick={() => setAllDeps(!allDeps)}>
            Every dependency
          </button>
          <button
            type="button"
            className="z-chip-button"
            aria-pressed={lineageOnly}
            disabled={!selected}
            onClick={() => setLineageOnly(!lineageOnly)}
          >
            Lineage only
          </button>
          <span className="explorer__zoom">
            <button type="button" className="z-chip-button" onClick={() => flow.fitView({ padding: 0.06, maxZoom: 1, duration: reduced ? 0 : 260 })}>
              Fit
            </button>
            <button type="button" className="z-chip-button" aria-label="Zoom in" onClick={() => flow.zoomIn({ duration: reduced ? 0 : 160 })}>
              +
            </button>
            <button type="button" className="z-chip-button" aria-label="Zoom out" onClick={() => flow.zoomOut({ duration: reduced ? 0 : 160 })}>
              −
            </button>
          </span>
        </div>
        {runControl}
      </div>
      <div className="explorer__stage" ref={stageRef} style={{ height: stageHeight }}>
        <div
          className="explorer__canvas"
          ref={canvasRef}
          role="group"
          aria-label={`${title}. Select a node to read its instruction, inputs and output. Drag to pan; pinch or use the buttons to zoom.`}
        >
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={NODE_TYPES}
            edgeTypes={EDGE_TYPES}
            nodesDraggable={false}
            nodesConnectable={false}
            nodesFocusable={false}
            edgesFocusable={false}
            elementsSelectable={false}
            minZoom={0.2}
            maxZoom={1.8}
            zoomOnDoubleClick={false}
            preventScrolling={false}
            zoomOnScroll={false}
            panOnScroll={false}
            proOptions={{ hideAttribution: true }}
            onPaneClick={() => selected && select(null)}
          />
          {!selected && <p className="explorer__hint">Select any node to read its instruction, inputs and output.</p>}
        </div>
        {selected && (
          <Inspector
            graph={graph}
            nodeId={selected}
            run={run ?? null}
            onNavigate={navigate}
            onClose={() => {
              const was = selected;
              select(null);
              setLineageOnly(false);
              window.requestAnimationFrame(() =>
                canvasRef.current?.querySelector<HTMLButtonElement>(`[data-node-id="${was}"]`)?.focus(),
              );
            }}
          />
        )}
      </div>
      <Legend
        states={states}
        hasTool={graph.nodes.some((n) => n.type === 'tool')}
        hasCheckpoint={graph.nodes.some((n) => CHECKPOINTS.has(n.id))}
        hasSkip={edges.some((e) => String(e.className).includes('z-edge--skip'))}
        hasOrigin={graph.nodes.some((n) => n.demo_provenance)}
      />
    </div>
  );
}

function Legend({
  states,
  hasTool,
  hasCheckpoint,
  hasSkip,
  hasOrigin,
}: {
  states: Record<string, NodeState> | null;
  hasTool: boolean;
  hasCheckpoint: boolean;
  hasSkip: boolean;
  hasOrigin: boolean;
}) {
  const present = states ? Array.from(new Set(Object.values(states))) : [];
  const order: NodeState[] = ['success', 'loaded', 'pending', 'failure', 'not_started', 'not_reached', 'unknown'];
  return (
    <div className="legend" aria-label="Key">
      <span className="legend__item">
        <span className="legend__swatch legend__swatch--reasoning" aria-hidden="true" /> Model call
      </span>
      {hasTool && (
        <span className="legend__item">
          <span className="legend__swatch legend__swatch--tool" aria-hidden="true" /> Tool
        </span>
      )}
      {hasCheckpoint && (
        <span className="legend__item">
          <span className="legend__swatch legend__swatch--checkpoint" aria-hidden="true" /> Frozen checkpoint
        </span>
      )}
      {hasSkip && (
        <span className="legend__item">
          <svg width="26" height="8" aria-hidden="true"><path d="M1 4h24" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" /></svg>
          Skips a step
        </span>
      )}
      {hasOrigin && (
        <span className="legend__item">
          <span className="z-origin z-origin--real_saved_input">Real input</span>
          <span className="z-origin z-origin--authored_synthetic">Synthetic</span>
          <span className="z-origin z-origin--derived_mixed_inputs">Derived</span>
          feed data
        </span>
      )}
      {order
        .filter((s) => present.includes(s))
        .map((s) => (
          <span key={s} className={`legend__item z-state z-state--${s}`}>
            <span className="z-state__glyph" aria-hidden="true" />
            {STATE_LABEL[s]}
          </span>
        ))}
    </div>
  );
}

function NodeSearch({ graph, onPick }: { graph: Graph; onPick: (id: string) => void }) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const listId = `search-${graph.mission}`;
  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    const all = graph.nodes.map((n) => ({ id: n.id, name: nodeName(n.id), lane: n.lane }));
    if (!q) return all.slice(0, 40);
    return all.filter((n) => n.name.toLowerCase().includes(q) || n.id.includes(q) || laneLabel(n.lane).toLowerCase().includes(q));
  }, [graph, query]);
  const pick = (id: string) => {
    onPick(id);
    setQuery('');
    setOpen(false);
  };
  return (
    <div className="search">
      <label className="visually-hidden" htmlFor={`${listId}-input`}>
        Find a node
      </label>
      <input
        id={`${listId}-input`}
        className="search__input"
        placeholder={`Find one of ${graph.node_count} nodes`}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={open && matches[active] ? `${listId}-${matches[active].id}` : undefined}
        value={query}
        onFocus={() => setOpen(true)}
        onBlur={() => window.setTimeout(() => setOpen(false), 120)}
        onChange={(event) => {
          setQuery(event.target.value);
          setActive(0);
          setOpen(true);
        }}
        onKeyDown={(event) => {
          if (event.key === 'ArrowDown') {
            event.preventDefault();
            setActive((a) => Math.min(a + 1, matches.length - 1));
          } else if (event.key === 'ArrowUp') {
            event.preventDefault();
            setActive((a) => Math.max(a - 1, 0));
          } else if (event.key === 'Enter' && matches[active]) {
            event.preventDefault();
            pick(matches[active].id);
          } else if (event.key === 'Escape') {
            setOpen(false);
          }
        }}
      />
      {open && matches.length > 0 && (
        <ul className="search__list" id={listId} role="listbox">
          {matches.map((match, index) => (
            <li
              key={match.id}
              id={`${listId}-${match.id}`}
              role="option"
              aria-selected={index === active}
              className="search__option"
              style={{ ['--lane' as string]: laneColor(match.lane) }}
              onMouseDown={(event) => {
                event.preventDefault();
                pick(match.id);
              }}
            >
              <span className="z-dot" aria-hidden="true" />
              {match.name}
              <span className="search__lane">{laneLabel(match.lane)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// Phone layout: the same graph as an ordered list of steps. Every node keeps
// a readable label, and the inspector opens as a full-screen sheet.
function StagedExplorer(props: ExplorerProps) {
  const { graph, run, runControl, title } = props;
  const everything = useMemo(() => {
    const families = layoutGraph(graph, new Set()).families;
    return layoutGraph(graph, new Set(families.keys()));
  }, [graph]);
  const { selected, select } = useSelection(props, everything.families);
  const states = useRunStates(graph, run);
  const columns = useMemo(() => {
    const byColumn = new Map<number, typeof everything.items>();
    everything.items.forEach((item) => {
      if (!byColumn.has(item.column)) byColumn.set(item.column, []);
      byColumn.get(item.column)!.push(item);
    });
    return Array.from(byColumn.entries()).sort((a, b) => a[0] - b[0]);
  }, [everything]);

  useEffect(() => {
    if (!selected) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previous;
    };
  }, [selected]);

  return (
    <div className="staged" aria-label={title}>
      {runControl && <div className="staged__run">{runControl}</div>}
      <ol className="staged__steps">
        {columns.map(([column, items]) => (
          <li key={column} className="staged__step">
            <span className="staged__num">
              Step {column + 1}
              {items.length > 1 && <span className="staged__family">{stepTitle(items, graph.mission)}</span>}
            </span>
            <ul>
              {items.map((item) =>
                item.kind === 'node' ? (
                  <li key={item.id}>
                    <button
                      type="button"
                      className={`staged__node${states ? ` is-${states[item.id]}` : ''}`}
                      data-node-id={item.id}
                      style={{ ['--lane' as string]: laneColor(item.node.lane) }}
                      onClick={() => select(item.id)}
                    >
                      <span className="z-dot" aria-hidden="true" />
                      <span className="staged__name">{nodeName(item.id)}</span>
                      <span className="staged__lane">{nodeRole(item.id, graph.mission) || laneLabel(item.node.lane)}</span>
                      {states && (
                        <span className={`z-state z-state--${states[item.id]}`}>
                          <span className="z-state__glyph" aria-hidden="true" />
                          {STATE_LABEL[states[item.id]]}
                        </span>
                      )}
                    </button>
                  </li>
                ) : null,
              )}
            </ul>
          </li>
        ))}
      </ol>
      {selected && (
        <div className="sheet" role="dialog" aria-modal="true" aria-label={`Details for ${nodeName(selected)}`}>
          <Inspector
            graph={graph}
            nodeId={selected}
            run={run ?? null}
            onNavigate={(id) => select(id)}
            onClose={() => select(null)}
          />
        </div>
      )}
    </div>
  );
}

function stepTitle(items: Array<{ id: string }>, mission: string): string {
  const labels = new Set(items.map((item) => nodeFamily(item.id, mission)?.label ?? ''));
  return labels.size === 1 ? [...labels][0] : '';
}
