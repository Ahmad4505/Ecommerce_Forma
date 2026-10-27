from pathlib import Path
import re
root=Path(__file__).resolve().parent.parent
p=root/'README.md'
text=p.read_text(encoding='utf-8')
text=text.replace('demo1234','Demo123!').replace('scripts/marketplace-vite.mjs','scripts/forma-run.mjs').replace('dist/','dist-forma/')
text=re.sub(r'^Development defaults.*$', 'Development defaults to http://127.0.0.1:5175. Preview defaults to http://127.0.0.1:4175. If a port is occupied, Vite prints the next available port. Browser tests use `playwright.forma.config.js` and default to port 5175; set `PLAYWRIGHT_BASE_URL` to use another URL. They use an installed Windows Chrome; set `CHROME_PATH` or update the configuration for another machine.',text,flags=re.M)
text=text.replace('Remote Unsplash photographs are illustrative and may differ from described products; unavailable images use the supplied SVG fallback. Google Fonts and remote photography require network access.','Unsplash photographs are cached locally in `public/images/` for dependable loading. They are illustrative and may differ from described products; unavailable user-supplied images use the supplied SVG fallback. Google Fonts and user-supplied remote images require network access.')
text=text.replace('tests/browser/flows.spec.js','tests/browser/flows.spec.js and workspaces.spec.js')
text=text.replace('## Verification','The standard entry `src/main.jsx` imports `src/marketplace-main.jsx`. The active service, store, and seed modules use the `marketplace` prefix. The Vite launcher uses an isolated `.forma-vite-cache` so concurrent local servers cannot overwrite its optimized dependencies. The production output is `dist-forma/`.\n\n## Verification')
p.write_text(text,encoding='utf-8')
