import type {CSSProperties} from 'react';
import type {Design, FontSpec} from './types';

// Design sizes are authored for 1080 px on the short edge; scale for others.
export const unit = (size: {width: number; height: number}) => Math.min(size.width, size.height) / 1080;

export const font = (f: FontSpec, u: number, extra: CSSProperties = {}): CSSProperties => ({
  fontFamily: `"${f.family}", system-ui, sans-serif`,
  fontWeight: f.weight,
  fontSize: f.size_px * u,
  lineHeight: 1.2,
  ...extra,
});

export const zoneColor = (design: Design, kind: 'internal' | 'external') =>
  kind === 'internal' ? design.palette.zone_internal : design.palette.zone_external;

export const withAlpha = (hex: string, alpha: number) => {
  const h = hex.replace('#', '');
  const n = parseInt(h.length === 3 ? h.split('').map((c) => c + c).join('') : h, 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
};
