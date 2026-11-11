import React from 'react';
import {AbsoluteFill, Easing, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {font, unit, withAlpha} from '../theme';
import type {Design} from '../types';

// Liquid text morph. Both words are blurred in opposite directions and an
// alpha-threshold filter snaps the blur back to hard edges, so letters appear
// to melt from one word into the other. The filter is applied only while the
// morph is running; before and after, the text renders crisp and antialiased.
//
// Timeline (fractions of the scene): `from` enters → hold → morph (~30-55%)
// → underline draws, glow blooms, tagline rises → hold to the end.
export const Morph: React.FC<{from: string; to: string; kicker?: string; tagline?: string; design: Design}> = ({
  from,
  to,
  kicker,
  tagline,
  design,
}) => {
  const frame = useCurrentFrame();
  const {fps, width, height, durationInFrames: D} = useVideoConfig();
  const u = unit({width, height});
  const p = design.palette;

  const m0 = Math.round(D * 0.25);
  const m1 = m0 + Math.round(Math.min(60, D * 0.35)); // ~2 s melt: long enough to read as deliberate
  // Linear on purpose: the blended "melt" lives in the middle of the range, and
  // an ease-in-out curve would rush straight through it.
  const f = interpolate(frame, [m0, m1], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const morphing = f > 0 && f < 1;

  const enter = spring({frame, fps, config: {damping: 200}, durationInFrames: 24});
  const k = 14 * u; // blur strength, tuned for the 132 px wordmark
  const blurTo = f > 0 ? Math.min(k / f - k, 100 * u) : 100 * u;
  const blurFrom = f < 1 ? Math.min(k / (1 - f) - k, 100 * u) : 100 * u;
  const opTo = Math.pow(f, 0.4);
  const opFrom = Math.pow(1 - f, 0.4);

  const after = (start: number, len: number) =>
    interpolate(frame, [m1 + start, m1 + start + len], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
  const rule = after(2, 22);
  const tag = after(12, 20);
  const glow = interpolate(frame, [m0, m1, m1 + 30], [0, 1, 0.7], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const scale = interpolate(f, [0, 1], [1, 1.03]);

  const wordStyle = font(design.typography.heading, u, {
    fontSize: 132 * u,
    letterSpacing: -2 * u,
    color: p.text,
    whiteSpace: 'nowrap',
    position: 'absolute',
    left: '50%',
    top: '50%',
    transform: 'translate(-50%, -50%)',
  });

  return (
    <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
      <svg width={0} height={0} style={{position: 'absolute'}}>
        <defs>
          <filter id="ff-threshold">
            <feColorMatrix in="SourceGraphic" type="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 255 -140" />
          </filter>
        </defs>
      </svg>

      <AbsoluteFill
        style={{
          background: `radial-gradient(ellipse 38% 30% at 50% 50%, ${withAlpha(p.accent, 0.28)}, transparent 70%)`,
          opacity: glow,
        }}
      />

      {kicker ? (
        <div
          style={{
            position: 'absolute',
            top: height / 2 - 150 * u,
            ...font(design.typography.mono, u, {fontSize: 26 * u, letterSpacing: 6 * u, color: p.muted, opacity: enter}),
          }}
        >
          {kicker.toUpperCase()}
        </div>
      ) : null}

      <div
        style={{
          position: 'relative',
          width: '100%',
          height: 200 * u,
          opacity: enter,
          transform: `translateY(${(1 - enter) * 30 * u}px) scale(${scale})`,
          filter: morphing ? 'url(#ff-threshold)' : undefined,
        }}
      >
        {f < 1 ? <div style={{...wordStyle, opacity: opFrom, filter: morphing ? `blur(${blurFrom}px)` : undefined}}>{from}</div> : null}
        {f > 0 ? <div style={{...wordStyle, opacity: opTo, filter: morphing ? `blur(${blurTo}px)` : undefined}}>{to}</div> : null}
      </div>

      <div
        style={{
          position: 'absolute',
          top: height / 2 + 105 * u,
          height: 6 * u,
          width: 320 * u * rule,
          borderRadius: 3 * u,
          background: `linear-gradient(90deg, ${p.accent}, ${p.zone_external})`,
        }}
      />
      {tagline ? (
        <div
          style={{
            position: 'absolute',
            top: height / 2 + 140 * u,
            ...font(design.typography.body, u, {color: p.muted, opacity: tag, transform: `translateY(${(1 - tag) * 16 * u}px)`}),
          }}
        >
          {tagline}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
