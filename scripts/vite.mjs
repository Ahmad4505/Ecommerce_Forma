// Restricted Windows environments may deny parent-directory realpath traversal.
// Only fall back for already-existing paths inside this checkout.
import fs from 'node:fs';
import path from 'node:path';
const root=process.cwd();
const original=fs.realpathSync;
function safeRealpath(value,...args){try{return original(value,...args)}catch(error){const resolved=path.resolve(String(value));if(error.code==='EPERM'&&(resolved===root||resolved.startsWith(root+path.sep))&&fs.existsSync(resolved))return resolved;throw error;}}
safeRealpath.native=safeRealpath;
if(process.env.FORMA_RESTRICTED_FS==='1')fs.realpathSync=safeRealpath;
const {build,createServer,preview}=await import('vite');
const {default:config}=await import('../vite.config.js');
const options={...config,configFile:false,resolve:{preserveSymlinks:true},esbuild:{tsconfigRaw:{compilerOptions:{jsx:'react-jsx'}}}};
const mode=process.argv[2]||'dev';
if(mode==='build')await build(options);
else if(mode==='preview'){const server=await preview({...options,preview:{host:'127.0.0.1'}});server.printUrls();}
else{const server=await createServer({...options,server:{host:'127.0.0.1'},optimizeDeps:{esbuildOptions:{preserveSymlinks:true,tsconfigRaw:{compilerOptions:{jsx:'react-jsx'}}}}});await server.listen();server.printUrls();}
