import React from 'react';
import {AbsoluteFill, useVideoConfig} from 'remotion';
import {unit, withAlpha} from './theme';
import type {Design} from './types';

// Static backdrop shared by every scene: dot grid fading toward the edges, two
// soft colour glows, and a vignette. It never animates, so it is identical on
// both sides of every cut, and segments stay independently cacheable.
export const Background: React.FC<{design: Design}> = ({design}) => {
  const {width, height} = useVideoConfig();
  const u = unit({width, height});
  const bg = design.background ?? {};
  const p = design.palette;

  if (bg.style !== 'grid-glow') {
    return <AbsoluteFill style={{backgroundColor: p.background}} />;
  }
  const grid = (bg.grid_px ?? 48) * u;
  // Sized and toned to survive social-platform re-encoding without getting busy.
  const dot = Math.max(1, 2.2 * u);

  return (
    <AbsoluteFill style={{backgroundColor: p.background}}>
      {bg.glow !== false ? (
        <>
          <AbsoluteFill style={{background: `radial-gradient(ellipse 55% 60% at 82% 12%, ${withAlpha(p.accent, 0.16)}, transparent 70%)`}} />
          <AbsoluteFill style={{background: `radial-gradient(ellipse 50% 55% at 8% 95%, ${withAlpha(p.zone_external, 0.09)}, transparent 70%)`}} />
        </>
      ) : null}
      <svg width={width} height={height} style={{position: 'absolute', inset: 0}}>
        <defs>
          <pattern id="ff-grid" width={grid} height={grid} patternUnits="userSpaceOnUse">
            <circle cx={grid / 2} cy={grid / 2} r={dot} fill={withAlpha(p.text, 0.2)} />
          </pattern>
          <radialGradient id="ff-grid-fade" cx="50%" cy="45%" r="70%">
            <stop offset="0%" stopColor="white" stopOpacity="1" />
            <stop offset="100%" stopColor="white" stopOpacity="0" />
          </radialGradient>
          <mask id="ff-grid-mask">
            <rect width={width} height={height} fill="url(#ff-grid-fade)" />
          </mask>
        </defs>
        <rect width={width} height={height} fill="url(#ff-grid)" mask="url(#ff-grid-mask)" />
      </svg>
      <AbsoluteFill style={{background: `radial-gradient(ellipse 80% 80% at 50% 50%, transparent 55%, ${withAlpha('#000000', 0.45)} 100%)`}} />
    </AbsoluteFill>
  );
};
