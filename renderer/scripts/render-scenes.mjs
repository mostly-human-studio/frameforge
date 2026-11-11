// Render a batch of FrameForge scenes. Invoked by the Python orchestrator:
//   node scripts/render-scenes.mjs <job.json>
// Emits one JSON object per line on stdout; errors go to stderr with exit 1.
//
// Telemetry: Remotion's renderer sends a usage event to remotion.pro whenever
// a licenseKey is passed, including "free-license". FrameForge never passes one,
// so nothing leaves the machine. Logging is set to "error", which also hides
// the resulting "Pass licenseKey" warning. tests/test_renderer_contract.py
// guards this.

import {existsSync, readFileSync, renameSync, rmSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {renderMedia, selectComposition} from '@remotion/renderer';

const here = path.dirname(fileURLToPath(import.meta.url));
const emit = (obj) => process.stdout.write(JSON.stringify(obj) + '\n');

const main = async () => {
  const jobPath = process.argv[2];
  if (!jobPath) throw new Error('usage: render-scenes.mjs <job.json>');
  const job = JSON.parse(readFileSync(jobPath, 'utf-8'));
  const entryPoint = path.resolve(here, '..', 'src', 'index.ts');

  let serveUrl = job.bundleDir;
  if (!existsSync(path.join(serveUrl, 'index.html'))) {
    emit({event: 'bundling'});
    const tmp = `${serveUrl}.tmp-${process.pid}`;
    rmSync(tmp, {recursive: true, force: true});
    await bundle({entryPoint, outDir: tmp, publicDir: job.publicDir ?? null, enableCaching: false});
    rmSync(serveUrl, {recursive: true, force: true});
    renameSync(tmp, serveUrl);
  }
  emit({event: 'bundled', serveUrl});

  const browser = job.browserExecutable ?? null;
  for (const scene of job.scenes) {
    emit({event: 'scene-start', id: scene.id});
    const composition = await selectComposition({
      serveUrl,
      id: 'Scene',
      inputProps: scene.props,
      browserExecutable: browser,
      chromeMode: job.chromeMode ?? 'headless-shell',
      logLevel: 'error',
    });
    // Render to a temporary name and rename only on success: an interrupted
    // render must never leave a short-but-playable file at the cached path.
    const partial = scene.output.replace(/\.mp4$/, '.partial.mp4');
    await renderMedia({
      serveUrl,
      composition,
      inputProps: scene.props,
      codec: 'h264',
      crf: job.crf ?? 18,
      x264Preset: job.x264Preset ?? 'veryfast',
      pixelFormat: 'yuv420p',
      muted: true,
      outputLocation: partial,
      overwrite: true,
      concurrency: job.concurrency ?? null,
      scale: job.scale ?? 1,
      browserExecutable: browser,
      chromeMode: job.chromeMode ?? 'headless-shell',
      logLevel: 'error',
      onProgress: ({progress}) => {
        if (Math.round(progress * 100) % 25 === 0) emit({event: 'progress', id: scene.id, progress});
      },
    });
    renameSync(partial, scene.output);
    emit({event: 'scene-done', id: scene.id, output: scene.output, frames: composition.durationInFrames});
  }
  emit({event: 'done'});
};

main().catch((err) => {
  process.stderr.write(`${err?.stack ?? err}\n`);
  process.exit(1);
});
