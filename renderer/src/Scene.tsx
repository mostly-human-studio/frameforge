import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {ensureFonts} from './fonts';
import {ArchitectureDiagram} from './templates/ArchitectureDiagram';
import {ImageScene} from './templates/ImageScene';
import {TextReveal} from './templates/TextReveal';
import {Title} from './templates/Title';
import type {SceneProps} from './types';

ensureFonts();

// Scene-level in/out transitions live inside each scene so rendered segments
// can be concatenated without cross-scene blending (see PLAN.md §2.3).
export const Scene: React.FC<SceneProps> = ({scene, design}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const fin = design.motion.scene_in.type === 'fade' ? design.motion.scene_in.frames : 0;
  const fout = design.motion.scene_out.type === 'fade' ? design.motion.scene_out.frames : 0;
  const opacity = Math.min(
    fin > 0 ? interpolate(frame, [0, fin], [0, 1], {extrapolateRight: 'clamp'}) : 1,
    fout > 0 ? interpolate(frame, [durationInFrames - fout, durationInFrames], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : 1,
  );

  let body: React.ReactNode;
  switch (scene.template) {
    case 'title':
      body = <Title {...scene.props} design={design} />;
      break;
    case 'text-reveal':
      body = <TextReveal {...scene.props} design={design} />;
      break;
    case 'architecture-diagram':
      body = <ArchitectureDiagram {...scene.props} design={design} />;
      break;
    case 'image':
      body = <ImageScene {...scene.props} design={design} />;
      break;
    default: {
      const t: never = scene;
      throw new Error(`Unknown template: ${JSON.stringify(t)}`);
    }
  }

  return (
    <AbsoluteFill style={{backgroundColor: design.palette.background}}>
      <AbsoluteFill style={{opacity}}>{body}</AbsoluteFill>
    </AbsoluteFill>
  );
};
