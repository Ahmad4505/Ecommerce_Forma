import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
const root=process.cwd();const lock=JSON.parse(fs.readFileSync('package-lock.json','utf8'));let count=0;const missing=[];
for(const [key,pkg] of Object.entries(lock.packages)){if(!key||!pkg.integrity||pkg.os&&!pkg.os.includes('win32')||pkg.cpu&&!pkg.cpu.includes('x64'))continue;const digest=Buffer.from(pkg.integrity.split('-')[1],'base64').toString('hex');const archive=path.join(root,'.npm-cache/_cacache/content-v2/sha512',digest.slice(0,2),digest.slice(2,4),digest.slice(4));if(!fs.existsSync(archive)){missing.push(key);continue;}const dest=path.resolve(root,key);if(!dest.startsWith(root+path.sep))throw Error('Path outside workspace');fs.mkdirSync(dest,{recursive:true});const result=spawnSync('tar.exe',['-xzf',archive,'-C',dest,'--strip-components=1'],{encoding:'utf8'});if(result.status!==0)console.log('FAILED',key,result.stderr?.slice(0,120));else count++;}
console.log('Restored packages from verified npm cache:',count,'Missing archives:',missing);
