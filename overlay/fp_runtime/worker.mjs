import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { Resvg, initWasm } from '@resvg/resvg-wasm';
import { validateRequest, validateFrame, stableStringify, sha256, ensureStatic } from './lib/contracts.mjs';
import { inspectFont, requireGlyphCoverage } from './lib/fonts.mjs';
const ROOT=path.dirname(fileURLToPath(import.meta.url));
const COMMIT='c568776bab8128ea02703fc7960203c58077ff0e';
const MAX=2*1024*1024;
async function main() {
  let raw='';
  process.stdin.setEncoding('utf8');
  for await (const chunk of process.stdin) {
    raw+=chunk;
    if (Buffer.byteLength(raw)>MAX) throw Error('Input exceeds 2 MiB');
  }
  const req=JSON.parse(raw);validateRequest(req);
  const kitRoot=path.resolve(process.env.FP_KIT_ROOT || path.join(ROOT,'fp-kit'));
  const themeId=req.input.theme ?? 'fp-v1';
  const themePath=path.join(kitRoot,'themes',themeId+'.json');
  const themeBytes=fs.readFileSync(themePath);
  // A light pack is the measured difference from the dark one, so the receipt has to pin
  // every file in the inheritance chain; pinning the leaf alone would let the base change
  // under a rendered result without the fingerprint moving.
  const themeChain=[themeId];
  for (let next=JSON.parse(themeBytes).extends; next; ) {
    if (themeChain.includes(next) || themeChain.length>4) throw Error('Theme pack inherits in a cycle');
    themeChain.push(next);
    next=JSON.parse(fs.readFileSync(path.join(kitRoot,'themes',next+'.json'))).extends;
  }
  const fp=await import(pathToFileURL(path.join(kitRoot,'dist/src/index.js')).href);
  // Original FP compiler: no substitute renderer or hardcoded template implementation.
  const result=fp.render(req.input);
  if (!result.audit?.ok) throw Error('FP audit failed: '+JSON.stringify(result.audit).slice(0,5000));
  validateFrame(result.program.frame);
  const textSvg=fp.toSvg(result.program);ensureStatic(textSvg);
  if (Buffer.byteLength(textSvg)>8*1024*1024) throw Error('Source SVG exceeds 8 MiB');
  await initWasm(fs.readFileSync(path.join(ROOT,'node_modules/@resvg/resvg-wasm/index_bg.wasm')));
  const fontDir=path.resolve(process.env.FP_FONT_DIR || path.join(ROOT,'fonts'));
  const fontFiles=fs.readdirSync(fontDir).filter(n=>/\.(ttf|otf)$/i.test(n)).sort();
  if (!fontFiles.length || fontFiles.length>24) throw Error('Supply 1-24 Pretendard TTF/OTF files');
  let totalFontBytes=0;
  const fonts=fontFiles.map(name=>{
    const full=path.join(fontDir,name);const st=fs.lstatSync(full);
    if (!st.isFile() || st.size>32*1024*1024) throw Error('Invalid font file');
    totalFontBytes+=st.size;
    if(totalFontBytes>96*1024*1024) throw Error('Total font bytes exceed 96 MiB');
    const bytes=fs.readFileSync(full);
    return {name,bytes,sha256:sha256(bytes)};
  });
  const inspectedFonts=fonts.map(f=>inspectFont(f.bytes));
  requireGlyphCoverage(textSvg,inspectedFonts);
  const font={fontBuffers:fonts.map(f=>new Uint8Array(f.bytes)),defaultFontFamily:'Pretendard'};
  const outliner=new Resvg(textSvg,{font});let svg;
  try {
    if (outliner.imagesToResolve().length) throw Error('External images refused');
    svg=outliner.toString();
  } finally {outliner.free();}
  if (/<text(?:\s|>)/i.test(svg)) throw Error('Unoutlined text remains');
  ensureStatic(svg);
  if (Buffer.byteLength(svg)>32*1024*1024) throw Error('Outlined SVG exceeds 32 MiB');
  const raster=new Resvg(svg,{font,fitTo:{mode:'original'}});let png;
  try {
    validateFrame({width:raster.width,height:raster.height});
    const image=raster.render();
    try {png=Buffer.from(image.asPng());} finally {image.free();}
  } finally {raster.free();}
  if (png.byteLength>32*1024*1024) throw Error('PNG exceeds 32 MiB');
  const themeFiles=fs.readdirSync(path.join(kitRoot,'themes')).filter(n=>themeChain.some(id=>n.startsWith(id+'.'))).sort();
  const theme={id:themeId,sha256:sha256(themeBytes),inherits:themeChain.slice(1),
    assets:themeFiles.map(n=>({name:n,sha256:sha256(fs.readFileSync(path.join(kitRoot,'themes',n)))}))};
  const fontReceipts=fonts.map(({name,sha256})=>({name,sha256}));
  // Pin bytes and versions, not an unsupported promise of cross-renderer pixel equality.
  function codeFiles(dir,base=dir) {
    return fs.readdirSync(dir,{withFileTypes:true}).sort((a,b)=>a.name.localeCompare(b.name,'en')).flatMap(e=>{
      const p=path.join(dir,e.name);
      if(e.isSymbolicLink()) throw Error('SDK symlink refused');
      return e.isDirectory()?codeFiles(p,base):(e.name.endsWith('.js')?[{path:path.relative(base,p),sha256:sha256(fs.readFileSync(p))}]:[]);
    });
  }
  const fingerprint={compiler:COMMIT,runtime:'0.3.0',node:process.version,resvg:'2.6.2',
    code:codeFiles(path.join(kitRoot,'dist/src')),theme,fonts:fontReceipts};
  // The delivered SVG is outlined glyphs, so the frame has to say what it drew itself.
  process.stdout.write(JSON.stringify({ok:true,svg,png_base64:png.toString('base64'),
    input_hash:sha256(stableStringify(req.input)),compiler:'fp-kit/'+COMMIT,
    renderer_fingerprint:sha256(stableStringify(fingerprint)),frame:result.program.frame,
    layout:fp.describeProgram(result,req.input),
    audit:result.audit,theme,fonts:fontReceipts}));
}
main().catch(e=>{
  process.stdout.write(JSON.stringify({ok:false,error:String(e?.message||e).slice(0,6000)}));
  process.exitCode=1;
});
