import { describe, it, expect } from 'vitest';
import { LatestArtifactReader } from './latestArtifact';
function deferred<T>() { let resolve!: (x: T) => void; let reject!: (x: unknown) => void;
  const promise = new Promise<T>((ok,bad) => {resolve=ok;reject=bad;});return {promise,resolve,reject}; }
describe('stock artifact viewer request order',()=>{
  it('late old response cannot overwrite a newer preview',async()=>{
    const a=deferred<string>(), b=deferred<string>();const values:string[]=[];
    let count=0;const r=new LatestArtifactReader(()=>count++ ? b.promise:a.promise);
    const one=r.read('s','a.svg',v=>values.push(v));const two=r.read('s','a.svg',v=>values.push(v));
    b.resolve('new');await two;a.resolve('old');await one;expect(values).toEqual(['new']);
  });
  it('session change/unmount invalidates pending work',async()=>{
    const a=deferred<string>();const values:string[]=[];const r=new LatestArtifactReader(()=>a.promise);
    const run=r.read('s1','a.svg',v=>values.push(v));r.invalidate();a.resolve('old-session');await run;
    expect(values).toEqual([]);
  });
  it('transient reload failure preserves the last good picture',async()=>{
    const values=['last-good'];const r=new LatestArtifactReader<string>(()=>Promise.reject(Error('network')));
    await r.read('s','a.svg',v=>values.push(v));expect(values).toEqual(['last-good']);
  });
});
