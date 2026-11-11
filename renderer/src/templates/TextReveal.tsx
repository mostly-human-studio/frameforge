import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {font, unit, withAlpha} from '../theme';
import type {Design} from '../types';

// Bullets are spread across the first ~60% of the scene so they land roughly
// while the narration talks about them.
export const TextReveal: React.FC<{heading: string; bullets: string[]; design: Design}> = ({heading, bullets, design}) => {
  const frame = useCurrentFrame();
  const {fps, width, height, durationInFrames} = useVideoConfig();
  const u = unit({width, height});
  const m = design.layout.safe_margin_px * u;

  const headIn = spring({frame, fps, config: {damping: 200}, durationInFrames: 20});
  const first = 18;
  const span = Math.max(0, durationInFrames * 0.6 - first);
  const gap = Math.max(design.motion.element_stagger_frames * 2, bullets.length > 1 ? span / (bullets.length - 1) : 0);

  return (
    <AbsoluteFill style={{padding: m, justifyContent: 'center'}}>
      <div style={font(design.typography.heading, u, {color: design.palette.text, opacity: headIn, transform: `translateX(${(1 - headIn) * -30 * u}px)`})}>
        {heading}
      </div>
      <div style={{height: 48 * u}} />
      {bullets.map((b, i) => {
        const start = first + i * gap;
        const p = spring({frame: frame - start, fps, config: {damping: 200}, durationInFrames: 18});
        const dim = interpolate(frame, [start + gap, start + gap + 10], [1, 0.55], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
        const isLast = i === bullets.length - 1;
        return (
          <div
            key={i}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 28 * u,
              margin: `${14 * u}px 0`,
              opacity: p * (isLast ? 1 : dim),
              transform: `translateY(${(1 - p) * 24 * u}px)`,
            }}
          >
            <div style={{width: 14 * u, height: 14 * u, borderRadius: 7 * u, background: design.palette.accent, boxShadow: `0 0 ${18 * u}px ${withAlpha(design.palette.accent, 0.6)}`, flexShrink: 0}} />
            <div style={font(design.typography.body, u, {color: design.palette.text})}>{b}</div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};
