import test from 'node:test';
import assert from 'node:assert/strict';
import { stableStringify, sha256, validateFrame, validateRequest, ensureStatic } from '../lib/contracts.mjs';
test('nested fields are retained in content hash',()=>{
  assert.notEqual(sha256(stableStringify({blocks:[{value:10}]})),sha256(stableStringify({blocks:[{value:11}]})));
});
test('key order is irrelevant recursively',()=>{
  assert.equal(stableStringify({b:1,a:{z:2,c:3}}),stableStringify({a:{c:3,z:2},b:1}));
});
test('array order and value type are meaningful',()=>{
  assert.notEqual(stableStringify([1,2]),stableStringify([2,1]));
  assert.notEqual(stableStringify('00123'),stableStringify(123));
});
for(const v of [null,[],undefined,1]) test(`invalid request ${JSON.stringify(v)}`,()=>assert.throws(()=>validateRequest({input:v})));
for(const n of [NaN,Infinity,Number.MAX_SAFE_INTEGER+1]) test(`unsafe number ${n}`,()=>assert.throws(()=>stableStringify(n)));
test('prototype keys rejected',()=>assert.throws(()=>validateRequest({input:JSON.parse('{"__proto__":{}}')})));
test('theme path traversal rejected',()=>assert.throws(()=>validateRequest({input:{theme:'../../x'}})));
test('valid frame',()=>validateFrame({width:1920,height:1080}));
for (const f of [{width:1920,height:20000},{width:0,height:10},{width:20.2,height:10},{width:8192,height:8192}]) test(`invalid frame ${JSON.stringify(f)}`,()=>assert.throws(()=>validateFrame(f)));
for(const svg of ['<svg><script/></svg>','<svg><foreignObject/></svg>','<svg><use href="https://x"/></svg>']) test(`unsafe SVG ${svg}`,()=>assert.throws(()=>ensureStatic(svg)));
test('static path supported',()=>ensureStatic('<svg><path d="M0 0L1 1"/></svg>'));
