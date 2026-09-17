import test from 'node:test';import assert from 'node:assert/strict';
import {inspectFont,requireGlyphCoverage} from '../lib/fonts.mjs';
// Synthetic table bytes only. Not a usable font, no glyph outlines or font files shipped.
function fixture(family='Pretendard',format=12){
  const string=Buffer.from(family,'utf16le');string.swap16();
  const name=Buffer.alloc(18+string.length);name.writeUInt16BE(1,2);name.writeUInt16BE(18,4);
  name.writeUInt16BE(3,6);name.writeUInt16BE(1,8);name.writeUInt16BE(0x409,10);name.writeUInt16BE(1,12);name.writeUInt16BE(string.length,14);string.copy(name,18);
  let cmap=Buffer.alloc(40);cmap.writeUInt16BE(1,2);cmap.writeUInt16BE(3,4);cmap.writeUInt16BE(10,6);cmap.writeUInt32BE(12,8);
  cmap.writeUInt16BE(12,12);cmap.writeUInt32BE(28,16);cmap.writeUInt32BE(1,24);cmap.writeUInt32BE(65,28);cmap.writeUInt32BE(90,32);cmap.writeUInt32BE(1,36);
  if(format===4){
    cmap=Buffer.alloc(44);cmap.writeUInt16BE(1,2);cmap.writeUInt16BE(3,4);cmap.writeUInt16BE(1,6);cmap.writeUInt32BE(12,8);
    const c=12;cmap.writeUInt16BE(4,c);cmap.writeUInt16BE(32,c+2);cmap.writeUInt16BE(4,c+6);
    cmap.writeUInt16BE(90,c+14);cmap.writeUInt16BE(0xffff,c+16);
    cmap.writeUInt16BE(65,c+20);cmap.writeUInt16BE(0xffff,c+22);
    cmap.writeUInt16BE(0xffc0,c+24);cmap.writeUInt16BE(1,c+26);
  }
  const b=Buffer.alloc(44+name.length+cmap.length);b.writeUInt32BE(0x00010000);b.writeUInt16BE(2,4);
  b.write('name',12);b.writeUInt32BE(44,20);b.writeUInt32BE(name.length,24);
  b.write('cmap',28);b.writeUInt32BE(44+name.length,36);b.writeUInt32BE(cmap.length,40);
  name.copy(b,44);cmap.copy(b,44+name.length);return b;
}
test('SFNT family and format12 glyph coverage',()=>{const f=inspectFont(fixture());assert.ok(f.has(65));assert.ok(!f.has(97));});
test('wrong font family is rejected',()=>assert.throws(()=>inspectFont(fixture('Other Font'))));
test('missing Korean glyph is not silently outlined away',()=>assert.throws(()=>requireGlyphCoverage('<svg><text>가</text></svg>',[inspectFont(fixture())])));
test('known glyph and whitespace accepted',()=>requireGlyphCoverage('<svg><text>A Z</text></svg>',[inspectFont(fixture())]));
test('malformed tables rejected',()=>assert.throws(()=>inspectFont(Buffer.alloc(16))));

test('format4 BMP segments enforce real glyph coverage',()=>{const f=inspectFont(fixture('Pretendard',4));assert.ok(f.has(65));assert.ok(f.has(90));assert.ok(!f.has(97));assert.ok(!f.has(0x1f300));assert.ok(!f.has(0xffff));});
