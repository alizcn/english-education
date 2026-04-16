"""Normalize AI-generated quiz items before they reach the DB / UI.

AI sometimes returns multiple-choice items in messy formats:
  - choices prefixed with "A. ", "B) ", etc.
  - correct_answer as just a letter ("A") while choices carry the full text
  - choices as bare letters ["A","B","C","D"] with the actual options baked into
    the prompt as "... A) foo B) bar C) baz D) qux"
  - empty / null / non-string entries mixed into choices

This module cleans those up so UI rendering and answer matching stay sane.
"""
import re


LABEL_RE = re.compile(r'^\s*([A-Da-d])\s*[\.\)\:\-]\s+')
LETTER_ONLY_RE = re.compile(r'^[A-Da-d]$')
INLINE_OPTIONS_RE = re.compile(
    r'(?:^|\s)([A-Da-d])\s*[\.\)\:\-]\s*(.+?)(?=\s+[A-Da-d]\s*[\.\)\:\-]\s|\s*$)',
    re.DOTALL,
)


def _as_text(v) -> str:
    if v is None:
        return ''
    if isinstance(v, dict):
        for key in ('text', 'label', 'value', 'option', 'answer'):
            if v.get(key):
                return str(v[key]).strip()
        return ''
    return str(v).strip()


def _clean_choices(raw):
    if not isinstance(raw, list):
        return []
    cleaned = []
    for item in raw:
        s = _as_text(item)
        if s:
            cleaned.append(s)
    return cleaned


def _strip_labels(choices):
    """Return (stripped_choices, letter_to_text_map)."""
    mapping = {}
    stripped = []
    for c in choices:
        m = LABEL_RE.match(c)
        if m:
            letter = m.group(1).upper()
            text = LABEL_RE.sub('', c, count=1).strip()
            stripped.append(text)
            mapping[letter] = text
        else:
            stripped.append(c)
    return stripped, mapping


def _extract_inline_options(prompt):
    """Pull 'A) foo B) bar ...' style options out of the prompt.

    Returns (cleaned_prompt, {letter: text}) when at least two letters are
    found; otherwise (prompt, {}).
    """
    matches = INLINE_OPTIONS_RE.findall(prompt)
    if len(matches) < 2:
        return prompt, {}
    mapping = {}
    for letter, text in matches:
        mapping[letter.upper()] = text.strip().rstrip('.,;:').strip()
    cleaned = INLINE_OPTIONS_RE.sub('', prompt).strip()
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned, mapping


def _resolve_correct(correct, choices, label_map):
    """If correct is a letter, map it to the matching choice text."""
    if not correct:
        return correct
    if not LETTER_ONLY_RE.match(correct):
        return correct
    letter = correct.upper()
    if letter in label_map:
        return label_map[letter]
    idx = 'ABCD'.index(letter)
    if idx < len(choices):
        return choices[idx]
    return correct


def normalize_item(item):
    """Return a cleaned copy of a single quiz item dict."""
    if not isinstance(item, dict):
        return item
    out = dict(item)
    prompt = _as_text(out.get('prompt'))
    correct = _as_text(out.get('correct_answer'))
    qtype = out.get('question_type') or ''

    if qtype == 'multiple_choice':
        choices = _clean_choices(out.get('choices'))
        choices, label_map = _strip_labels(choices)

        if choices and all(LETTER_ONLY_RE.match(c) for c in choices):
            new_prompt, inline_map = _extract_inline_options(prompt)
            if inline_map:
                prompt = new_prompt
                choices = [inline_map.get(c.upper(), c) for c in choices]
                label_map = {**label_map, **inline_map}

        correct = _resolve_correct(correct, choices, label_map)
        out['choices'] = choices or None
    else:
        out['choices'] = None

    out['prompt'] = prompt
    out['correct_answer'] = correct
    return out


def normalize_items(items):
    return [normalize_item(it) for it in (items or []) if isinstance(it, dict)]
