import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {evolvePath, getLength, getPointAtLength} from '@remotion/paths';
import {font, unit, withAlpha, zoneColor} from '../theme';
import type {Design, DiagramNode, Edge, Zone} from '../types';

type Box = {node: DiagramNode; zone: Zone; cx: number; cy: number; w: number; h: number; order: number};

// Layout: zones are columns (left→right, in storyboard order) sized by node
// count; nodes sit in a row inside their zone. Edges between neighbours are
// straight; edges that would cross another node arc over the top. Opposite
// edges between the same pair are offset so both stay readable.
// Reveal order: zones → nodes → edges (in list order), across ~75% of the scene.
export const ArchitectureDiagram: React.FC<{heading?: string; zones: Zone[]; nodes: DiagramNode[]; edges: Edge[]; design: Design}> = ({
  heading,
  zones,
  nodes,
  edges,
  design,
}) => {
  const frame = useCurrentFrame();
  const {fps, width, height, durationInFrames} = useVideoConfig();
  const u = unit({width, height});
  const m = design.layout.safe_margin_px * u;
  const stagger = design.motion.element_stagger_frames;

  const top = m + (heading ? 150 * u : 40 * u);
  const bottom = height - m;
  const zoneGap = 56 * u;
  const counts = zones.map((z) => Math.max(1, nodes.filter((n) => n.zone === z.id).length));
  const totalUnits = counts.reduce((a, b) => a + b, 0);
  const usable = width - 2 * m - zoneGap * (zones.length - 1);

  // Zones hug their content (nodes + headroom for arcs and labels) instead of
  // filling the frame, and sit centred in the space below the heading.
  const cy = (top + bottom) / 2 + 30 * u;
  const zoneH = Math.min(bottom - top, 560 * u);
  let x = m;
  const zoneRects = zones.map((z, i) => {
    const w = (usable * counts[i]) / totalUnits;
    const r = {zone: z, x, y: cy - zoneH / 2, w, h: zoneH};
    x += w + zoneGap;
    return r;
  });
  const boxes: Box[] = [];
  zoneRects.forEach((zr) => {
    const members = nodes.filter((n) => n.zone === zr.zone.id);
    const slot = zr.w / Math.max(1, members.length);
    members.forEach((n, j) => {
      boxes.push({node: n, zone: zr.zone, cx: zr.x + slot * (j + 0.5), cy, w: Math.min(340 * u, slot - 48 * u), h: 150 * u, order: 0});
    });
  });
  boxes.sort((a, b) => a.cx - b.cx).forEach((b, i) => (b.order = i));
  const byId = new Map(boxes.map((b) => [b.node.id, b]));

  // Timeline
  const zoneStart = (i: number) => i * stagger;
  const nodeStart = (i: number) => 12 + i * stagger * 2;
  // Every edge must finish drawing before the scene fades out, however short the scene.
  const edgesFrom = Math.min(nodeStart(boxes.length) + 10, durationInFrames * 0.4);
  const available = Math.max(6, durationInFrames * 0.8 - edgesFrom);
  const edgeDraw = Math.max(4, Math.min(22, available / Math.max(1, edges.length)));
  const edgeGap = edges.length > 1 ? (available - edgeDraw) / (edges.length - 1) : 0;

  const pairCount = new Map<string, number>();
  const pairSeen = new Map<string, number>();
  edges.forEach((e) => {
    const k = [e.from, e.to].sort().join('|');
    pairCount.set(k, (pairCount.get(k) ?? 0) + 1);
  });

  const headIn = spring({frame, fps, config: {damping: 200}, durationInFrames: 20});

  return (
    <AbsoluteFill>
      {heading ? (
        <div style={{position: 'absolute', left: m, top: m, ...font(design.typography.heading, u, {color: design.palette.text, opacity: headIn})}}>{heading}</div>
      ) : null}
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{position: 'absolute', inset: 0}}>
        {zoneRects.map((zr, i) => {
          const c = zoneColor(design, zr.zone.kind);
          const p = interpolate(frame, [zoneStart(i), zoneStart(i) + 15], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          return (
            <g key={zr.zone.id} opacity={p}>
              <rect
                x={zr.x}
                y={zr.y}
                width={zr.w}
                height={zr.h}
                rx={24 * u}
                fill={withAlpha(c, 0.07)}
                stroke={withAlpha(c, 0.7)}
                strokeWidth={3 * u}
                strokeDasharray={zr.zone.kind === 'external' ? `${14 * u} ${10 * u}` : undefined}
              />
              <text x={zr.x + 32 * u} y={zr.y + 56 * u} fill={c} style={font(design.typography.mono, u, {fontSize: 26 * u, letterSpacing: 2 * u})}>
                {zr.zone.label.toUpperCase()}
              </text>
            </g>
          );
        })}

        {edges.map((e, i) => {
          const a = byId.get(e.from);
          const b = byId.get(e.to);
          if (!a || !b) return null;
          const k = [e.from, e.to].sort().join('|');
          const nth = pairSeen.get(k) ?? 0;
          pairSeen.set(k, nth + 1);
          const total = pairCount.get(k) ?? 1;
          const offset = total > 1 ? (nth - (total - 1) / 2) * 44 * u : 0;
          const dir = Math.sign(b.cx - a.cx) || 1;
          const sx = a.cx + (dir * a.w) / 2;
          const ex = b.cx - (dir * b.w) / 2;
          const y = a.cy + offset;
          const neighbours = Math.abs(a.order - b.order) <= 1;
          const ctrlY = a.cy - a.h / 2 - 160 * u;
          const midX = (a.cx + b.cx) / 2;
          const d = neighbours
            ? `M ${sx} ${y} L ${ex} ${y}`
            : `M ${a.cx} ${a.cy - a.h / 2} Q ${midX} ${ctrlY} ${b.cx} ${b.cy - b.h / 2}`;

          const start = edgesFrom + i * edgeGap;
          const progress = interpolate(frame, [start, start + edgeDraw], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          if (progress <= 0) return null;
          const len = getLength(d);
          const evo = evolvePath(progress, d);
          const tip = getPointAtLength(d, Math.max(0, len * progress - 0.01)) ?? {x: ex, y};
          const back = getPointAtLength(d, Math.max(0, len * progress - 12 * u)) ?? {x: sx, y};
          const angle = Math.atan2(tip.y - back.y, tip.x - back.x);
          const style = e.style ?? 'request';
          const color = style === 'request' ? design.palette.accent : style === 'stream' ? design.palette.zone_external : design.palette.zone_internal;
          const drawn = progress >= 1;
          const streaming = style === 'stream' && drawn;
          const ah = 18 * u;
          const labelX = neighbours ? (sx + ex) / 2 : midX;
          // Paired edges: label above the upper line, below the lower one.
          const labelY = neighbours ? (offset > 0 ? y + 44 * u : y - 22 * u) : (a.cy - a.h / 2 + ctrlY) / 2 - 10 * u;
          // Shrink labels to fit the gap between boxes (monospace ≈ 0.6em per char), never below 16 px.
          const room = neighbours ? Math.abs(ex - sx) - 16 * u : 520 * u;
          const labelSize = e.label ? Math.max(16 * u, Math.min(24 * u, room / (e.label.length * 0.6))) : 0;
          const labelW = e.label ? e.label.length * labelSize * 0.6 + 16 * u : 0;
          const labelOpacity = interpolate(progress, [0.4, 1], [0, 1], {extrapolateLeft: 'clamp'});

          return (
            <g key={i}>
              <path
                d={d}
                fill="none"
                stroke={color}
                strokeWidth={5 * u}
                strokeLinecap="round"
                strokeDasharray={streaming ? `${16 * u} ${12 * u}` : evo.strokeDasharray}
                strokeDashoffset={streaming ? -(frame - start - edgeDraw) * 2 * u : evo.strokeDashoffset}
              />
              <polygon
                points={`0,0 ${-ah},${-ah * 0.55} ${-ah},${ah * 0.55}`}
                fill={color}
                transform={`translate(${tip.x} ${tip.y}) rotate(${(angle * 180) / Math.PI})`}
              />
              {!drawn ? <circle cx={tip.x} cy={tip.y} r={9 * u} fill={color} opacity={0.9} /> : null}
              {e.label ? (
                <g opacity={labelOpacity}>
                  <rect
                    x={labelX - labelW / 2}
                    y={labelY - labelSize * 1.05}
                    width={labelW}
                    height={labelSize * 1.5}
                    rx={6 * u}
                    fill={withAlpha(design.palette.background, 0.85)}
                  />
                  <text x={labelX} y={labelY} textAnchor="middle" fill={design.palette.text} style={font(design.typography.mono, u, {fontSize: labelSize})}>
                    {e.label}
                  </text>
                </g>
              ) : null}
            </g>
          );
        })}

        {boxes.map((bx) => {
          const c = zoneColor(design, bx.zone.kind);
          const p = spring({frame: frame - nodeStart(bx.order), fps, config: {damping: 200}, durationInFrames: 18});
          return (
            <g key={bx.node.id} opacity={p} transform={`translate(0 ${(1 - p) * 20 * u})`}>
              <rect
                x={bx.cx - bx.w / 2}
                y={bx.cy - bx.h / 2}
                width={bx.w}
                height={bx.h}
                rx={18 * u}
                fill={design.palette.surface}
                stroke={c}
                strokeWidth={4 * u}
              />
              <text x={bx.cx} y={bx.cy + 12 * u} textAnchor="middle" fill={design.palette.text} style={font(design.typography.body, u, {fontWeight: 600, fontSize: 34 * u})}>
                {bx.node.label}
              </text>
            </g>
          );
        })}
      </svg>
    </AbsoluteFill>
  );
};
