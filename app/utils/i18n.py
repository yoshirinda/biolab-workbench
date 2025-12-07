import os
import json
from functools import lru_cache

TRANSLATIONS_DIR = os.path.join(os.path.dirname(__file__), '..', 'translations')


@lru_cache()
def load_translations():
    data = {}
    try:
        for fname in os.listdir(TRANSLATIONS_DIR):
            if fname.endswith('.json'):
                lang = fname.rsplit('.', 1)[0]
                path = os.path.join(TRANSLATIONS_DIR, fname)
                with open(path, 'r', encoding='utf-8') as f:
                    data[lang] = json.load(f)
    except Exception:
        pass
    return data


def get_translations_for(lang: str):
    data = load_translations()
    if lang in data:
        return data[lang]
    # fallback to english
    return data.get('en', {})


def t(key: str, lang: str = None):
    """Simple translation getter. Key is dot-separated."""
    if lang is None:
        lang = os.environ.get('BIOLAB_LANG', 'en')
    trans = get_translations_for(lang)
    parts = key.split('.')
    cur = trans
    for p in parts:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return key
    return cur
