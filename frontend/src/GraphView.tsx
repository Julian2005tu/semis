import { useEffect, useState } from 'react';
import type { CSSProperties } from 'react';
import { ReactFlow, Controls, Background, MarkerType, Position } from '@xyflow/react';
import type { Node as FlowNode, Edge as FlowEdge } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from 'dagre';
import { fetchUpstream } from './api';
import type { Confidence, Mode } from './api';
import type { PathEntry } from './App';
import SupplyNode from './SupplyNode';
import type { SupplyNodeData } from './SupplyNode';

const nodeWidth = 220;
const nodeHeight = 66; // room for the "N sites" chip
const nodeTypes = { supply: SupplyNode };

// Edge styling by confidence: high solid, medium lighter, low dashed.
const EDGE_STYLE: Record<Confidence, CSSProperties> = {
  high: { stroke: '#94a3b8', strokeWidth: 2 },
  medium: { stroke: '#94a3b8', strokeWidth: 2, opacity: 0.45 },
  low: { stroke: '#94a3b8', strokeWidth: 1.5, strokeDasharray: '6 4' },
};

// A node can feed the focus through several edges (TSMC → Nvidia: wafers and CoWoS). We draw one
// arrow per node, styled by its best-sourced edge; the tooltip lists every edge.
function bestConfidence(levels: (Confidence | null)[]): Confidence {
  return (['high', 'medium', 'low'] as const).find((c) => levels.includes(c)) ?? 'low';
}

function layout(nodes: FlowNode[], edges: FlowEdge[]): FlowNode[] {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: 'LR', nodesep: 14, ranksep: 140 });
  nodes.forEach((n) => g.setNode(n.id, { width: nodeWidth, height: nodeHeight }));
  edges.forEach((e) => g.setEdge(e.source, e.target));
  dagre.layout(g);
  return nodes.map((n) => {
    const { x, y } = g.node(n.id);
    return {
      ...n,
      targetPosition: Position.Left,
      sourcePosition: Position.Right,
      position: { x: x - nodeWidth / 2, y: y - nodeHeight / 2 },
    };
  });
}

function toGraph(focusNode: SupplyNodeData, upstream: { id: string; data: SupplyNodeData; confidence: Confidence }[]) {
  const focusId = '__focus__';
  const nodes: FlowNode[] = [
    { id: focusId, type: 'supply', data: focusNode, position: { x: 0, y: 0 } },
  ];
  const edges: FlowEdge[] = [];
  upstream.forEach((up, i) => {
    nodes.push({
      id: up.id,
      type: 'supply',
      data: { ...up.data, delay: Math.min(i * 25, 400) },
      position: { x: 0, y: 0 },
    });
    edges.push({
      id: `e-${up.id}`,
      source: up.id,
      target: focusId,
      style: EDGE_STYLE[up.confidence],
      markerEnd: { type: MarkerType.ArrowClosed, width: 18, height: 18, color: '#94a3b8' },
    });
  });
  return { nodes: layout(nodes, edges), edges };
}

export default function GraphView({
  focus,
  mode,
  context,
  onSelect,
  onShowEvents,
}: {
  focus: PathEntry;
  mode: Mode;
  context?: string;
  onSelect: (entry: PathEntry) => void;
  onShowEvents: (entry: PathEntry) => void;
}) {
  const [graph, setGraph] = useState<{ nodes: FlowNode[]; edges: FlowEdge[] } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);

    const load = async () => {
      if (mode === 'specific') {
        const res = await fetchUpstream(focus.id, 'specific', context);
        const focusEntry = { ...focus, name: res.focus.name };
        return toGraph(
          {
            title: res.focus.name,
            subtitle: res.focus.category,
            isFocus: true,
            eventCount: res.focus.event_count,
            onShowEvents: () => onShowEvents(focusEntry),
          },
          res.upstream.map((up) => {
            const entry = { id: up.id, name: up.name, label: up.label };
            return {
              id: up.id,
              confidence: bestConfidence(up.edges.map((e) => e.confidence)),
              data: {
                title: up.name,
                subtitle: up.category,
                edges: up.edges,
                eventCount: up.event_count,
                siteCount: up.site_count,
                onClick: () => onSelect(entry),
                onShowEvents: () => onShowEvents(entry),
              },
            };
          }),
        );
      }
      // General mode: the server sends no names, so the focus title comes from our own path.
      const res = await fetchUpstream(focus.id, 'general', context);
      return toGraph(
        { title: focus.name, subtitle: res.focus.category, isFocus: true },
        res.upstream.map((up) => ({
          id: `role:${up.role}`,
          confidence: bestConfidence(up.confidences),
          data: {
            title: up.role,
            subtitle: `${up.supplier_count} supplier${up.supplier_count === 1 ? '' : 's'}`,
          },
        })),
      );
    };

    load()
      .then((g) => !cancelled && setGraph(g))
      .catch(() => !cancelled && setError('Could not load this level.'));
    return () => {
      cancelled = true;
    };
  }, [focus, mode, context, onSelect, onShowEvents]);

  return (
    <div className="graph-frame">
      {error ? (
        <div className="graph-message">{error}</div>
      ) : !graph ? (
        <div className="graph-message">Loading…</div>
      ) : (
        <ReactFlow
          // Remount per level so fitView re-centres and the entry animation replays.
          key={`${focus.id}|${mode}|${context ?? ''}`}
          nodes={graph.nodes}
          edges={graph.edges}
          nodeTypes={nodeTypes}
          nodesDraggable={false}
          nodesConnectable={false}
          fitView
          fitViewOptions={{ padding: 0.15, maxZoom: 1.2 }}
          minZoom={0.1}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#334155" gap={16} />
          <Controls showInteractive={false} />
        </ReactFlow>
      )}
      {graph?.nodes.length === 1 && (
        <div className="graph-note">No inputs recorded for this node yet — the seed data stops here.</div>
      )}
      <div className="legend">
        <span><svg width="28" height="6"><line x1="0" y1="3" x2="28" y2="3" style={EDGE_STYLE.high} /></svg>high</span>
        <span><svg width="28" height="6"><line x1="0" y1="3" x2="28" y2="3" style={EDGE_STYLE.medium} /></svg>medium</span>
        <span><svg width="28" height="6"><line x1="0" y1="3" x2="28" y2="3" style={EDGE_STYLE.low} /></svg>low (unverified)</span>
      </div>
    </div>
  );
}
