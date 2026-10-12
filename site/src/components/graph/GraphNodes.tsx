// Node renderers for the graph explorer. Adapted from CustomNode,
// ContainerNode and GroupBackingNode in the original Zenith GraphViewer:
// status reads through border style plus a printed label (never colour
// alone), emphasis tiers dim the background, and containers expand on click.
// Each card is a real <button> so keyboard and screen-reader users can reach it.
import { memo } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import type { GraphNode } from '../../api';
import { laneColor, laneLabel } from '../../lib/lanes';
import { CHECKPOINTS, nodeName, nodeRole, type Family } from '../../lib/naming';
import { STATE_LABEL, type NodeState } from '../../lib/status';
import { originLabel } from '../../lib/provenance';

export type Emphasis = 'selected' | 'input' | 'consumer' | 'ancestor' | 'descendant' | 'background' | undefined;

export type ZNodeData = {
  node: GraphNode;
  mission: string;
  state: NodeState | null;
  emphasis: Emphasis;
  onSelect: (id: string) => void;
};

export type ZGroupData = {
  family: Family;
  members: GraphNode[];
  lanes: string[];
  state: NodeState | null;
  emphasis: Emphasis;
  onExpand: (key: string) => void;
};

export type ZFrameData = {
  family: Family;
  count: number;
  onCollapse: (key: string) => void;
};

const handleStyle = { opacity: 0, width: 1, height: 1, border: 0, minWidth: 0, minHeight: 0 };

function StateMark({ state }: { state: NodeState | null }) {
  if (!state) return null;
  return (
    <span className={`z-state z-state--${state}`}>
      <span className="z-state__glyph" aria-hidden="true" />
      {STATE_LABEL[state]}
    </span>
  );
}

export const ZNode = memo(function ZNode({ data }: NodeProps<ZNodeData>) {
  const { node, mission, state, emphasis, onSelect } = data;
  const kind = node.type === 'tool' ? 'Tool' : 'Model call';
  const role = nodeRole(node.id, mission);
  const checkpoint = CHECKPOINTS.has(node.id);
  const origin = originLabel(node.demo_provenance);
  return (
    <div
      className={`z-node z-node--${node.type === 'tool' ? 'tool' : 'reasoning'}${checkpoint ? ' z-node--checkpoint' : ''}${state ? ` is-${state}` : ''}${emphasis ? ` em-${emphasis}` : ''}`}
      style={{ ['--lane' as string]: laneColor(node.lane) }}
    >
      <Handle type="target" position={Position.Left} style={handleStyle} isConnectable={false} />
      <button
        type="button"
        className="z-node__hit"
        data-node-id={node.id}
        aria-pressed={emphasis === 'selected'}
        aria-label={`${nodeName(node.id)}, ${laneLabel(node.lane)}, ${kind}${origin ? `, ${origin}` : ''}${state ? `, ${STATE_LABEL[state]}` : ''}. Open details.`}
        title={`${nodeName(node.id)}: open its instruction, inputs and output`}
        onClick={(event) => {
          event.stopPropagation();
          onSelect(node.id);
        }}
      >
        <span className="z-node__top">
          <span className="z-node__name">{nodeName(node.id)}</span>
          {origin && <span className={`z-origin z-origin--${node.demo_provenance!.input_origin}`}>{origin}</span>}
        </span>
        <span className="z-node__role">{role}</span>
        <span className="z-node__foot">
          {node.lane !== 'SPINE' ? (
            <span className="z-node__lane">
              <span className="z-dot" aria-hidden="true" />
              {laneLabel(node.lane)}
            </span>
          ) : checkpoint ? (
            <span className="z-node__lane z-node__lane--cp">Checkpoint node</span>
          ) : (
            <span />
          )}
          <StateMark state={state} />
        </span>
      </button>
      <Handle type="source" position={Position.Right} style={handleStyle} isConnectable={false} />
    </div>
  );
});

export const ZGroup = memo(function ZGroup({ data }: NodeProps<ZGroupData>) {
  const { family, members, lanes, state, emphasis, onExpand } = data;
  return (
    <div className={`z-group${state ? ` is-${state}` : ''}${emphasis ? ` em-${emphasis}` : ''}`}>
      <Handle type="target" position={Position.Left} style={handleStyle} isConnectable={false} />
      <button
        type="button"
        className="z-group__hit"
        data-group-key={family.key}
        aria-label={`${family.label}, ${members.length} nodes. Expand group.`}
        onClick={(event) => {
          event.stopPropagation();
          onExpand(family.key);
        }}
      >
        <span className="z-group__name">{family.label}</span>
        <span className="z-group__summary" title={lanes.map(laneLabel).join(', ')}>
          {family.summary}
        </span>
        <span className="z-group__state">
          <StateMark state={state} />
        </span>
        <span className="z-group__foot">
          <span className="z-group__count">{members.length} nodes</span>
          <span className="z-group__expand" aria-hidden="true">
            Expand
          </span>
        </span>
      </button>
      <Handle type="source" position={Position.Right} style={handleStyle} isConnectable={false} />
    </div>
  );
});

export const ZFrame = memo(function ZFrame({ data }: NodeProps<ZFrameData>) {
  return (
    <div className="z-frame">
      <Handle type="target" position={Position.Left} style={handleStyle} isConnectable={false} />
      <Handle type="source" position={Position.Right} style={handleStyle} isConnectable={false} />
      <span className="z-frame__label">
        {data.family.label}
        <button type="button" className="z-frame__collapse" onClick={() => data.onCollapse(data.family.key)}>
          Collapse
        </button>
      </span>
    </div>
  );
});

export type ZBandData = { title: string; detail: string };

export const ZBand = memo(function ZBand({ data }: NodeProps<ZBandData>) {
  return (
    <div className="z-band">
      <span className="z-band__title">{data.title}</span>
      {data.detail && <span className="z-band__detail">{data.detail}</span>}
    </div>
  );
});

export const NODE_TYPES = { znode: ZNode, zgroup: ZGroup, zframe: ZFrame, zband: ZBand };
