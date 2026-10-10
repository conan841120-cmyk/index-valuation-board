"""Serialize JSON for a JavaScript value inside an HTML script element."""
import json


def inline_json(value):
    text = json.dumps(value, ensure_ascii=False, allow_nan=False)
    for character, escape in [('&', '\\u0026'), ('<', '\\u003c'), ('>', '\\u003e'),
                              ('\u2028', '\\u2028'), ('\u2029', '\\u2029')]:
        text = text.replace(character, escape)
    return text
