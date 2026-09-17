/** Minimal SFNT identity/cmap preflight. Not a shaper, rasterizer or font-file validator.
 * OpenType name IDs 1/16 and Unicode cmap formats 4/12; rendering remains in resvg.
 */
export function inspectFont(buffer) {
  const b=Buffer.from(buffer);
  const need=(at,n)=>{if(at<0||n<0||at+n>b.length) throw Error('Malformed font table bounds');};
  const u16=at=>{need(at,2);return b.readUInt16BE(at);};
  const u32=at=>{need(at,4);return b.readUInt32BE(at);};
  need(0,12);
  if (![0x00010000,0x4f54544f].includes(u32(0))) throw Error('Expected a standalone TrueType/OpenType font');
  const tables=new Map();const count=u16(4);if(count>512) throw Error('Excessive font table count');
  for(let i=0;i<count;i++){
    const p=12+16*i;need(p,16);const tag=b.toString('ascii',p,p+4),at=u32(p+8),size=u32(p+12);
    need(at,size);tables.set(tag,{at,size});
  }
  const n=tables.get('name'),c=tables.get('cmap');if(!n||!c)throw Error('Font lacks name/cmap tables');
  const families=[];const nr=u16(n.at+2),strings=u16(n.at+4);if(nr>4096)throw Error('Excessive name records');
  for(let i=0;i<nr;i++){
    const p=n.at+6+i*12;const platform=u16(p),id=u16(p+6),len=u16(p+8),off=u16(p+10);
    if(![1,16].includes(id))continue;
    const start=n.at+strings+off;if(start+len>n.at+n.size)throw Error('Malformed font name');
    need(start,len);let text='';
    if(platform===0||platform===3){for(let j=0;j+1<len;j+=2)text+=String.fromCharCode(u16(start+j));}
    else text=b.toString('latin1',start,start+len);
    families.push(text);
  }
  if(!families.some(s=>/^Pretendard(?:\s|$)/i.test(s)))throw Error('Configured font is not a Pretendard family');
  const maps=[];const entries=u16(c.at+2);if(entries>1024)throw Error('Excessive cmap records');
  for(let i=0;i<entries;i++){
    const p=c.at+4+i*8,platform=u16(p),encoding=u16(p+2),at=c.at+u32(p+4);
    if(!(platform===0||(platform===3&&[1,10].includes(encoding))))continue;
    const format=u16(at);if(format!==4&&format!==12)continue;
    const len=format===12?u32(at+4):u16(at+2);
    if(at+len>c.at+c.size)throw Error('Malformed cmap bounds');
    maps.push({at,format,len});
  }
  maps.sort((a,b)=>b.format-a.format);
  const map=maps[0];if(!map)throw Error('Font has no supported Unicode cmap');
  const {at,format,len}=map;
  if(format===12){
    const groups=u32(at+12);if(16+groups*12>len)throw Error('Malformed cmap groups');
    return {families,has(cp){
      let lo=0,hi=groups-1;
      while(lo<=hi){const mid=(lo+hi)>>1,p=at+16+mid*12,a=u32(p),z=u32(p+4);
        if(cp<a)hi=mid-1;else if(cp>z)lo=mid+1;else return u32(p+8)+cp-a!==0;
      }return false;
    }};
  }
  const segs=u16(at+6)/2;if(!Number.isInteger(segs)||16+segs*8>len)throw Error('Malformed cmap segments');
  return {families,has(cp){
    if(cp>0xffff)return false;
    for(let i=0;i<segs;i++){
      if(cp>u16(at+14+i*2))continue;
      const start=u16(at+16+segs*2+i*2);if(cp<start)return false;
      const delta=u16(at+16+segs*4+i*2),pos=at+16+segs*6+i*2,off=u16(pos);
      if(!off)return ((cp+delta)&0xffff)!==0;
      const address=pos+off+(cp-start)*2;if(address+2>at+len)throw Error('Malformed glyph address');
      const gid=u16(address);return gid!==0&&((gid+delta)&0xffff)!==0;
    }return false;
  }};
}
export function requireGlyphCoverage(svg, fonts) {
  const names={amp:'&',lt:'<',gt:'>',quot:'"',apos:"'"};
  const text=svg.replace(/<[^>]*>/g,'').replace(/&(#x[0-9a-f]+|#\d+|amp|lt|gt|quot|apos);/gi,(_,e)=>{
    if(e[0]==='#')return String.fromCodePoint(e[1].toLowerCase()==='x'?parseInt(e.slice(2),16):parseInt(e.slice(1),10));
    return names[e];
  });
  const missing=[...new Set([...text])].filter(ch=>!/[\s\u200c\u200d\ufe0e\ufe0f]/u.test(ch)&&!fonts.some(f=>f.has(ch.codePointAt(0))));
  if(missing.length)throw Error('Missing font glyphs: '+missing.slice(0,24).map(c=>'U+'+c.codePointAt(0).toString(16).toUpperCase()).join(', '));
}
