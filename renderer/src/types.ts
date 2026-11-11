// Props contract between the Python orchestrator and the Remotion renderer.
// Python builds these from storyboard.json + design-system.yaml; keep in sync
// with src/frameforge/render/props.py.

export type Zone = {id: string; label: string; kind: 'internal' | 'external'};
export type DiagramNode = {id: string; label: string; zone: string; icon?: string};
export type Edge = {from: string; to: string; label?: string; style?: 'request' | 'response' | 'stream'};

export type TemplateProps =
  | {template: 'title'; props: {heading: string; subheading?: string}}
  | {template: 'text-reveal'; props: {heading: string; bullets: string[]}}
  | {template: 'architecture-diagram'; props: {heading?: string; zones: Zone[]; nodes: DiagramNode[]; edges: Edge[]}}
  | {template: 'image'; props: {asset: string; caption?: string; fit?: 'contain' | 'cover'}}
  | {template: 'morph'; props: {from: string; to: string; kicker?: string; tagline?: string}};

export type SceneSpec = {id: string; title?: string} & TemplateProps;

export type FontSpec = {family: string; weight: number; size_px: number};

export type Design = {
  name: string;
  version: number | string;
  palette: {
    background: string;
    surface: string;
    text: string;
    muted: string;
    accent: string;
    zone_internal: string;
    zone_external: string;
  };
  typography: {heading: FontSpec; body: FontSpec; mono: FontSpec};
  layout: {safe_margin_px: number};
  motion: {
    scene_in: {type: 'fade' | 'none'; frames: number};
    scene_out: {type: 'fade' | 'none'; frames: number};
    element_stagger_frames: number;
  };
  background?: {style?: 'plain' | 'grid-glow'; grid_px?: number; glow?: boolean};
};

export type SceneProps = {
  scene: SceneSpec;
  design: Design;
  timing: {fps: number; durationInFrames: number};
  size: {width: number; height: number};
};
