import fs from 'node:fs';
import path from 'node:path';
// Some restricted Windows sessions can read the checkout but cannot resolve
// its parent directories. Keep this fallback strictly inside this checkout.
const root=process.cwd();
const original=fs.realpathSync;
function scopedRealpath(value,...args){try{return original(value,...args)}catch(error){const resolved=path.resolve(String(value));if(error.code==='EPERM'&&(resolved===root||resolved.startsWith(root+path.sep))&&fs.existsSync(resolved))return resolved;throw error}}
scopedRealpath.native=scopedRealpath;
fs.realpathSync=scopedRealpath;
const {build,createServer,preview,resolveConfig}=await import('vite');
const {default:config}=await import('../vite.config.js');
const options={...config,configFile:false,resolve:{...config.resolve,preserveSymlinks:true},esbuild:{tsconfigRaw:{compilerOptions:{jsx:'react-jsx'}}}};
const mode=process.argv[2]||'dev';
const resolvedConfig=mode==='dev'?await resolveConfig(options,'serve'):null;
const resolveDependency=resolvedConfig?.createResolver({asSrc:false});
// Resolve optimizer imports through Node in restricted Windows workspaces.
// Native esbuild cannot traverse this machine's protected parent folders.
const workspaceResolver={name:'workspace-dependencies',setup(builder){
 builder.onResolve({filter:/.*/},async args=>{
  if(args.path.startsWith('node:'))return {path:args.path,external:true};
  try{const resolved=await resolveDependency(args.path,args.importer||path.join(root,'index.html'));if(resolved?.startsWith('__vite-browser-external'))return {path:args.path,external:true};if(resolved)return {path:resolved};return undefined;}catch{return undefined;}
 });
 builder.onLoad({filter:/\.[cm]?jsx?$/},args=>({contents:fs.readFileSync(args.path,'utf8'),loader:args.path.endsWith('jsx')?'jsx':'js',resolveDir:path.dirname(args.path)}));
}};
if(mode==='build')await build(options);
else if(mode==='preview'){const server=await preview({...options,preview:{host:'127.0.0.1',port:4173}});server.printUrls()}
else{const server=await createServer({...options,server:{host:'127.0.0.1',port:5173},optimizeDeps:{entries:['src/main.jsx'],esbuildOptions:{plugins:[workspaceResolver],preserveSymlinks:true,tsconfigRaw:{compilerOptions:{jsx:'react-jsx'}}}}});await server.listen();server.printUrls()}
