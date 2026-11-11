import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {font, unit} from '../theme';
import type {Design} from '../types';

export const Title: React.FC<{heading: string; subheading?: string; design: Design}> = ({heading, subheading, design}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const u = unit({width, height});
  const m = design.layout.safe_margin_px * u;

  const enter = spring({frame, fps, config: {damping: 200}, durationInFrames: 24});
  const rule = spring({frame: frame - 8, fps, config: {damping: 200}, durationInFrames: 30});
  const sub = interpolate(frame, [18, 36], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  return (
    <AbsoluteFill style={{justifyContent: 'center', padding: m}}>
      <div style={{transform: `translateY(${(1 - enter) * 40 * u}px)`, opacity: enter}}>
        <div style={font(design.typography.heading, u, {fontSize: design.typography.heading.size_px * 1.25 * u, color: design.palette.text, maxWidth: width - 2 * m})}>
          {heading}
        </div>
      </div>
      <div style={{height: 8 * u, width: 240 * u * rule, background: design.palette.accent, borderRadius: 4 * u, margin: `${32 * u}px 0`}} />
      {subheading ? (
        <div style={font(design.typography.body, u, {color: design.palette.muted, opacity: sub, maxWidth: width - 2 * m})}>{subheading}</div>
      ) : null}
    </AbsoluteFill>
  );
};
