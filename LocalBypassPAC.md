# LocalBypassPAC
[返回](https://github.com/wefio/inspiration/blob/main/README.md)
```bash
function FindProxyForURL(u,h){if(!this.__){const o='(25[0-5]|2[0-4]\\d|1\\d{2}|[1-9]\\d|\\d)';this.__={c:[
  /^localhost$/i,
  /^[a-z0-9-]+\.local$/i,
  new RegExp(`^127\\.${o}\\.${o}\\.${o}$`,'i'),
  new RegExp(`^10\\.${o}\\.${o}\\.${o}$`,'i'),
  new RegExp(`^172\\.(1[6-9]|2\\d|3[0-1])\\.${o}\\.${o}$`,'i'),
  new RegExp(`^192\\.168\\.${o}\\.${o}$`,'i'),
  /^(::1|fe80:(:[0-9a-f]{1,4}){0,4}%\w+)$/i
],p:"PROXY 127.0.0.1:%mixed-port%; SOCKS5 127.0.0.1:%mixed-port%; DIRECT;"};}

const c=((h)=>{try{
  let v=h.toLowerCase().replace(/[^\da-f:.-]/g,'');
  return v.startsWith('[')?v.slice(1,v.indexOf(']')):v.split(/[:%]/)[0];
}catch{return h&&h.toLowerCase().replace(/[^\w.:-]/g,'')||''}})(h);

return this.__.c.some(r=>r.test(c))?"DIRECT":this.__.p;}
```
<p>不代理私有IP地址（ipv4+ipv6）、localhost</p>
<p>非常快</p>
<p>没什么用</p>
<p>由ai生成</p>
