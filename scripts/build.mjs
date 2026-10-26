// Bundles src/ into www/app.js. `--serve` also starts a local dev server on port 5173.
import * as esbuild from 'esbuild';

const options = {
  entryPoints: ['src/main.js'],
  bundle: true,
  format: 'iife',
  target: ['chrome89'],
  outfile: 'www/app.js',
  sourcemap: process.argv.includes('--serve'),
  minify: !process.argv.includes('--serve'),
  logLevel: 'info',
};

if (process.argv.includes('--serve')) {
  const ctx = await esbuild.context(options);
  await ctx.watch();
  const { port } = await ctx.serve({ servedir: 'www', port: 5173 });
  console.log(`Dev server: http://localhost:${port}`);
} else {
  await esbuild.build(options);
}
