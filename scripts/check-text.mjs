import fs from 'node:fs';
for(const file of ['src/pages/Public.jsx','src/pages/Dashboard.jsx','src/components/StoreLayout.jsx','src/pages/DemoAuth.jsx','src/app/App.jsx']){const s=fs.readFileSync(file,'utf8');console.log(file,'double-encoded',s.includes('\u00c2'),'star?',s.match(/stars.{0,90}/)?.[0]);}
