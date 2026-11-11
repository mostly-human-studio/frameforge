import type {SceneProps} from './types';

// Default props for Remotion Studio previews only. Real renders get props from Python.
export const SAMPLE_PROPS: SceneProps = {
  scene: {
    id: 's02',
    template: 'architecture-diagram',
    props: {
      heading: 'Two sides of the line',
      zones: [
        {id: 'yours', label: 'Your app + backend', kind: 'internal'},
        {id: 'provider', label: 'Model provider', kind: 'external'},
      ],
      nodes: [
        {id: 'app', label: 'App UI', zone: 'yours'},
        {id: 'backend', label: 'Your backend', zone: 'yours'},
        {id: 'api', label: 'LLM API', zone: 'provider'},
      ],
      edges: [
        {from: 'app', to: 'backend', label: 'user question', style: 'request'},
        {from: 'backend', to: 'api', label: 'HTTPS request', style: 'request'},
        {from: 'api', to: 'backend', label: 'streamed tokens', style: 'stream'},
      ],
    },
  },
  design: {
    name: 'technical-dark',
    version: 1,
    palette: {
      background: '#0E1116',
      surface: '#161B22',
      text: '#E6EDF3',
      muted: '#8B949E',
      accent: '#58A6FF',
      zone_internal: '#2EA043',
      zone_external: '#D29922',
    },
    typography: {
      heading: {family: 'Inter', weight: 700, size_px: 72},
      body: {family: 'Inter', weight: 400, size_px: 40},
      mono: {family: 'JetBrains Mono', weight: 500, size_px: 32},
    },
    layout: {safe_margin_px: 96},
    motion: {scene_in: {type: 'fade', frames: 12}, scene_out: {type: 'fade', frames: 12}, element_stagger_frames: 6},
  },
  timing: {fps: 30, durationInFrames: 240},
  size: {width: 1920, height: 1080},
};
