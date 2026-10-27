import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
const root=process.cwd(),original=fs.realpathSync;
function scopedRealpath(value,...args){try{return original(value,...args)}catch(error){const resolved=path.resolve(String(value));if(error.code==='EPERM'&&(resolved===root||resolved.startsWith(root+path.sep))&&fs.existsSync(resolved))return resolved;throw error}}
scopedRealpath.native=scopedRealpath;fs.realpathSync=scopedRealpath;
const {build,createServer,preview,resolveConfig}=await import('vite');
const {default:config}=await import('../vite.config.js');
const entry={name:'forma-entry',transformIndexHtml:{order:'pre',handler:html=>html.replace('/src/main.jsx','/src/marketplace-main.jsx')}};
const options={...config,plugins:[...config.plugins,entry],cacheDir:'node_modules/.vite-forma',configFile:false,build:{...config.build,outDir:'dist-forma'},resolve:{...config.resolve,preserveSymlinks:true},esbuild:{tsconfigRaw:{compilerOptions:{jsx:'react-jsx'}}}};
const mode=process.argv[2]||'dev';
const option=(name,fallback)=>{const index=process.argv.indexOf(name);return index>=0?process.argv[index+1]:fallback};
if(mode==='build')await build(options);
else if(mode==='preview'){const server=await preview({...options,preview:{host:'127.0.0.1',port:4175}});server.printUrls()}
else{
 let localOrigin;
 if(!process.argv.includes('--port')){
  const python=process.platform==='win32'?'backend/.venv/Scripts/python.exe':'backend/.venv/bin/python';
  if(fs.existsSync(python)){
   const result=spawnSync(python,['scripts/frontend-config.py'],{encoding:'utf8'});
   if(result.status!==0)throw Error('Could not read Django frontend configuration. Check backend setup or specify --port explicitly.');
   const url=new URL(JSON.parse(result.stdout).frontendUrl);
   if(['localhost','127.0.0.1','[::1]'].includes(url.hostname))localOrigin=url;
  }
 }
 const devHost=option('--host',localOrigin?.hostname||'127.0.0.1');
 const devPort=Number(option('--port',localOrigin?.port||5175));
 const resolved=await resolveConfig(options,'serve');const resolveDependency=resolved.createResolver({asSrc:false});
 const resolver={name:'workspace-dependencies',setup(builder){builder.onResolve({filter:/.*/},async args=>{if(args.path.startsWith('node:'))return {path:args.path,external:true};try{const found=await resolveDependency(args.path,args.importer||path.join(root,'index.html'));if(found?.startsWith('__vite-browser-external'))return {path:args.path,external:true};return found?{path:found}:undefined}catch{return undefined}});builder.onLoad({filter:/\.[cm]?jsx?$/},args=>({contents:fs.readFileSync(args.path,'utf8'),loader:args.path.endsWith('jsx')?'jsx':'js',resolveDir:path.dirname(args.path)}))}};
 const server=await createServer({...options,server:{...config.server,host:devHost,port:devPort,strictPort:true},optimizeDeps:{include:['react','react-dom/client','react-router-dom','react-hot-toast','zustand','zustand/middleware','lucide-react','gsap','gsap/ScrollTrigger','axios','react-hook-form','@hookform/resolvers/zod','zod','@react-three/fiber','@react-three/drei'],entries:['src/marketplace-main.jsx'],esbuildOptions:{plugins:[resolver],preserveSymlinks:true,tsconfigRaw:{compilerOptions:{jsx:'react-jsx'}}}}});await server.listen();server.printUrls();
}
