import React from 'react';
import {Composition} from 'remotion';
import {Scene} from './Scene';
import {SAMPLE_PROPS} from './sample';
import type {SceneProps} from './types';

// One composition renders one scene. Duration and size come from props, so
// Python decides timing (from narration audio, from M3 on).
export const Root: React.FC = () => (
  <Composition
    id="Scene"
    component={Scene as unknown as React.FC<Record<string, unknown>>}
    defaultProps={SAMPLE_PROPS as unknown as Record<string, unknown>}
    durationInFrames={SAMPLE_PROPS.timing.durationInFrames}
    fps={SAMPLE_PROPS.timing.fps}
    width={SAMPLE_PROPS.size.width}
    height={SAMPLE_PROPS.size.height}
    calculateMetadata={({props}) => {
      const p = props as unknown as SceneProps;
      return {
        durationInFrames: p.timing.durationInFrames,
        fps: p.timing.fps,
        width: p.size.width,
        height: p.size.height,
      };
    }}
  />
);
