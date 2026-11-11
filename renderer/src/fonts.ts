// Fonts are bundled from npm (@fontsource), so rendering never fetches fonts
// from the network. Each weight is registered, then we hold the first frame
// until the browser has actually loaded them, or text would render in a
// fallback font on early frames (non-deterministic output).
import '@fontsource/inter/400.css';
import '@fontsource/inter/600.css';
import '@fontsource/inter/700.css';
import '@fontsource/jetbrains-mono/500.css';
import {continueRender, delayRender} from 'remotion';

let started = false;

export const ensureFonts = (): void => {
  if (started || typeof document === 'undefined') return;
  started = true;
  const handle = delayRender('Loading bundled fonts');
  Promise.all([
    document.fonts.load('400 40px Inter'),
    document.fonts.load('600 40px Inter'),
    document.fonts.load('700 72px Inter'),
    document.fonts.load('500 32px "JetBrains Mono"'),
  ])
    .then(() => document.fonts.ready)
    .then(() => continueRender(handle))
    .catch((err) => {
      console.error('Font loading failed', err);
      continueRender(handle);
    });
};
