from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import re, urllib.request
root = Path(__file__).resolve().parent.parent
files = [root/'src/data/marketplace.js'] + [root/'src/pages'/f for f in ['Home.jsx','Shop.jsx','Auth.jsx','Info.jsx']]
ids = set(re.findall(r'photo-[a-zA-Z0-9-]+', '\n'.join(p.read_text(encoding='utf-8') for p in files)))
folder = root/'public/images'
folder.mkdir(parents=True, exist_ok=True)
def download(image_id):
    target = folder/(image_id+'.jpg')
    if target.exists() and target.stat().st_size > 1000: return image_id, True
    try:
        width = 1600 if image_id == 'photo-1600210492486-724fe5c67fb0' else 900
        urllib.request.urlretrieve(f'https://images.unsplash.com/{image_id}?auto=format&fit=crop&w={width}&q=82', target)
        return image_id, True
    except Exception as e:
        print('Unavailable:', image_id, str(e), flush=True)
        return image_id, False
with ThreadPoolExecutor(max_workers=6) as pool:
    results = list(pool.map(download, sorted(ids)))
print(f'Cached {sum(ok for _,ok in results)} of {len(results)} image sources.', flush=True)
