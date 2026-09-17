const test=require('node:test');const assert=require('node:assert/strict');
const {LatestArtifactReader}=require('../validation/js/latestArtifact.js');
const defer=()=>{let resolve,reject;const promise=new Promise((r,j)=>{resolve=r;reject=j});return {promise,resolve,reject};};
test('out-of-order artifact response is discarded',async()=>{const a=defer(),b=defer();let n=0;const out=[];const r=new LatestArtifactReader(()=>n++?b.promise:a.promise);const p=r.read('s','x.svg',v=>out.push(v));const q=r.read('s','x.svg',v=>out.push(v));b.resolve('new');await q;a.resolve('old');await p;assert.deepEqual(out,['new']);});
test('old session read is cancelled',async()=>{const a=defer(),out=[];const r=new LatestArtifactReader(()=>a.promise);const p=r.read('s','x.svg',v=>out.push(v));r.invalidate();a.resolve('old');await p;assert.deepEqual(out,[]);});
test('transient reload preserves good image',async()=>{const out=['last-good'];const r=new LatestArtifactReader(()=>Promise.reject(Error('network')));await r.read('s','x.svg',v=>out.push(v));assert.deepEqual(out,['last-good']);});
