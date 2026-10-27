import fs from 'node:fs';
import path from 'node:path';
function walk(dir){for(const file of fs.readdirSync(dir,{withFileTypes:true})){const p=path.join(dir,file.name);if(file.isDirectory())walk(p);else if(/\.(jsx?|css|mjs)$/.test(p)){const bytes=fs.readFileSync(p);try{new TextDecoder('utf-8',{fatal:true}).decode(bytes)}catch{fs.writeFileSync(p,new TextDecoder('windows-1252').decode(bytes),'utf8');console.log('Converted',p)}}}}
walk('src');walk('scripts');
