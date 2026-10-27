from pathlib import Path
import re
root = Path(__file__).resolve().parent.parent
paths = [root/'index.html', root/'src/marketplace-main.jsx']
paths += list((root/'src/pages').glob('*.jsx'))
paths += list((root/'src/components').rglob('*.jsx'))
def repair(match):
    text = match.group()
    if not any(c in text for c in ['Ã','Â','â','ï','ð']): return text
    for _ in range(3):
        try:
            encoded = b''.join(c.encode('cp1252') if c not in '\u0081\u008d\u008f\u0090\u009d' else bytes([ord(c)]) for c in text)
            decoded = encoded.decode('utf-8')
            if decoded == text: break
            text = decoded
        except (UnicodeEncodeError, UnicodeDecodeError): break
    return text
for p in paths:
    source = p.read_text(encoding='utf-8')
    fixed = re.sub(r'[^\x00-\x7f]+', repair, source)
    if source != fixed:
        p.write_text(fixed,encoding='utf-8')
        print('Repaired text:',p.name)
