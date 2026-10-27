"""Expose only the public frontend origin to the local Vite launcher."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
from django.conf import settings

print(json.dumps({'frontendUrl': settings.FRONTEND_URL}))
