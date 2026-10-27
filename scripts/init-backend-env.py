from pathlib import Path
import secrets
root=Path(__file__).resolve().parents[1]
target=root/'backend/.env'
if target.exists():
    print('backend/.env already exists; preserved unchanged.')
else:
    text=(root/'backend/.env.example').read_text(encoding='utf-8')
    target.write_text(text.replace('replace-with-a-unique-random-secret',secrets.token_urlsafe(50)),encoding='utf-8')
    print('Created ignored backend/.env with a unique secret. Configure DATABASE_URL before migrating.')
