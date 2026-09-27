import { Handle, Position } from '@xyflow/react';
import type { NodeProps, Node } from '@xyflow/react';
import type { MouseEvent } from 'react';
import type { SupplyEdge } from './api';

export type SupplyNodeData = {
  title: string;
  subtitle?: string | null;
  isFocus?: boolean;
  edges?: SupplyEdge[]; // specific mode only: every edge from this node into the focus
  eventCount?: number;
  siteCount?: number; // specific mode only: production sites shown in Map mode
  delay?: number; // staggers the entry animation
  look?: 'planned' | 'historical'; // set when the node has no current edge into the focus
  onClick?: () => void; // absent in general mode: roles aren't nodes you can drill into
  onShowEvents?: () => void;
  onShowInfo?: () => void; // focus node only: opens the info panel
};

// Clicks inside the tooltip or on the badge must not also trigger the node's drill-down click.
const stop = (e: MouseEvent) => e.stopPropagation();

export default function SupplyNode({ data }: NodeProps<Node<SupplyNodeData>>) {
  const { title, subtitle, isFocus, edges, eventCount, siteCount, delay = 0, look, onClick, onShowEvents, onShowInfo } =
    data;

  return (
    <div
      className={`supply-node ${isFocus ? 'focus' : ''} ${onClick ? 'clickable' : ''} ${look ?? ''}`}
      style={{ animationDelay: `${delay}ms` }}
      onClick={onClick}
    >
      <Handle type="target" position={Position.Left} className="hidden-handle" />
      <div className="supply-node-title">{title}</div>
      {subtitle && <div className="supply-node-subtitle">{subtitle}</div>}
      {!!siteCount && <span className="site-chip">{siteCount} site{siteCount === 1 ? '' : 's'}</span>}
      <Handle type="source" position={Position.Right} className="hidden-handle" />

      {onShowInfo && (
        <button
          className="info-button"
          title="Details: capex, investments, sites"
          aria-label="Show details"
          onClick={(e) => {
            stop(e);
            onShowInfo();
          }}
        >
          ⓘ
        </button>
      )}

      {!!eventCount && onShowEvents && (
        <button
          className="event-badge"
          title={`${eventCount} ongoing/upcoming disruption${eventCount === 1 ? '' : 's'}`}
          onClick={(e) => {
            stop(e);
            onShowEvents();
          }}
        >
          {eventCount}
        </button>
      )}

      {edges && edges.length > 0 && (
        <div className="supply-tooltip nowheel" onClick={stop}>
          {edges.map((edge, i) => (
            <div key={i} className="supply-tooltip-row">
              <div className="supply-tooltip-item">
                {edge.item ?? edge.type.replace('_', ' ').toLowerCase()}
                {edge.status !== 'active' && <span className={`status-badge ${edge.status}`}>{edge.status}</span>}
              </div>
              {edge.share_estimate && <div>Share: {edge.share_estimate}</div>}
              <div>Confidence: <span className={`conf conf-${edge.confidence}`}>{edge.confidence ?? 'n/a'}</span></div>
              {edge.source_url && (
                <a href={edge.source_url} target="_blank" rel="noreferrer">
                  Source ↗
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
