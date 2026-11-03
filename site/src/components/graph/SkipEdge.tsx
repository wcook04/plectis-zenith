// Edges that skip a step or cross into the next band never run behind node
// cards: they leave through the gap right of the source column, travel in the
// channel above the target's band, and enter through the gap left of the
// target column. Each edge has its own slot, so parallel routes separate.
import { BaseEdge, type EdgeProps } from 'reactflow';

export type RoutedEdgeData = { channelY: number; slot: number; outLane: number };

function rounded(points: Array<[number, number]>, radius: number): string {
  let d = `M${points[0][0]} ${points[0][1]}`;
  for (let i = 1; i < points.length - 1; i++) {
    const [px, py] = points[i - 1];
    const [x, y] = points[i];
    const [nx, ny] = points[i + 1];
    const inLen = Math.hypot(x - px, y - py);
    const outLen = Math.hypot(nx - x, ny - y);
    const r = Math.min(radius, inLen / 2, outLen / 2);
    if (r < 0.5) {
      d += ` L${x} ${y}`;
      continue;
    }
    const ax = x - ((x - px) / inLen) * r;
    const ay = y - ((y - py) / inLen) * r;
    const bx = x + ((nx - x) / outLen) * r;
    const by = y + ((ny - y) / outLen) * r;
    d += ` L${ax} ${ay} Q${x} ${y} ${bx} ${by}`;
  }
  const last = points[points.length - 1];
  return `${d} L${last[0]} ${last[1]}`;
}

export function RoutedEdge({ id, sourceX, sourceY, targetX, targetY, data, style, markerEnd }: EdgeProps<RoutedEdgeData>) {
  const slot = data?.slot ?? 0;
  const channelY = data?.channelY ?? Math.min(sourceY, targetY) - 40;
  // Column gaps are 64px and expanded-group frames take 10px on each side,
  // so the vertical runs stay between 18px and 38px from the cards.
  const out = sourceX + 18 + 7 * ((data?.outLane ?? 0) % 4);
  const into = targetX - 18;
  void slot;
  const path = rounded(
    [
      [sourceX, sourceY],
      [out, sourceY],
      [out, channelY],
      [into, channelY],
      [into, targetY],
      [targetX, targetY],
    ],
    8,
  );
  return <BaseEdge id={id} path={path} style={style} markerEnd={markerEnd} />;
}

export type StackEdgeData = { width: number; slot: number };

// Cards stacked in one column connect through a bracket in the gap on the
// column's left, so the edge never crosses a card between them.
export function StackEdge({ id, sourceX, sourceY, targetY, data, style, markerEnd }: EdgeProps<StackEdgeData>) {
  const w = data?.width ?? 200;
  // Handles sit 4px outside the card, so the card's left edge is
  // sourceX - w - 4. The trunk runs 5px inside the group frame's 10px
  // padding, never on its border; every edge into one target shares it.
  const cardLeft = sourceX - w - 4;
  const x0 = cardLeft - 5;
  const path = rounded([[cardLeft, sourceY], [x0, sourceY], [x0, targetY], [cardLeft, targetY]], 4);
  return <BaseEdge id={id} path={path} style={style} markerEnd={markerEnd} />;
}

export const EDGE_TYPES = { routed: RoutedEdge, stack: StackEdge };
