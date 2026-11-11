import React from 'react';
import {AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {font, unit} from '../theme';
import type {Design} from '../types';

// Assets are served from the project's assets/ folder (Remotion public dir).
export const ImageScene: React.FC<{asset: string; caption?: string; fit?: 'contain' | 'cover'; design: Design}> = ({
  asset,
  caption,
  fit = 'contain',
  design,
}) => {
  const frame = useCurrentFrame();
  const {width, height, durationInFrames} = useVideoConfig();
  const u = unit({width, height});
  const m = design.layout.safe_margin_px * u;
  const zoom = interpolate(frame, [0, durationInFrames], [1, 1.05]);
  const capIn = interpolate(frame, [10, 25], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  return (
    <AbsoluteFill style={{padding: fit === 'cover' ? 0 : m, justifyContent: 'center', alignItems: 'center'}}>
      <Img
        src={staticFile(asset)}
        style={{width: '100%', height: caption ? '82%' : '100%', objectFit: fit, transform: `scale(${zoom})`, borderRadius: fit === 'cover' ? 0 : 16 * u}}
      />
      {caption ? (
        <div style={font(design.typography.body, u, {color: design.palette.muted, opacity: capIn, marginTop: 24 * u, textAlign: 'center'})}>{caption}</div>
      ) : null}
    </AbsoluteFill>
  );
};
