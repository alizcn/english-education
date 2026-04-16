import json
import logging
from typing import Iterable
from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)

_client: OpenAI | None = None


def client() -> OpenAI:
    global _client
    if _client is None:
        if not settings.OPENAI_API_KEY:
            raise RuntimeError('OPENAI_API_KEY .env dosyasında tanımlı değil.')
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


def _chat_json(system: str, user: str) -> dict:
    resp = client().chat.completions.create(
        model=settings.OPENAI_MODEL,
        response_format={'type': 'json_object'},
        messages=[
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user},
        ],
    )
    content = resp.choices[0].message.content or '{}'
    return json.loads(content)


def translate_words(words: Iterable[str]) -> list[dict]:
    cleaned = [w.strip() for w in words if w and w.strip()]
    if not cleaned:
        return []
    system = (
        'You are an English-Turkish dictionary assistant. For each English word or phrase, '
        'return its Turkish meaning, a short natural example sentence in English, and the '
        'Turkish translation of that sentence, plus a short part-of-speech tag '
        '(noun, verb, adj, adv, phrase...). Every entry must have a non-empty Turkish '
        'translation — never return an empty turkish field. Respond ONLY in the requested JSON format.'
    )
    user = (
        'Return JSON: {"items": [{"english": "...", "turkish": "...", '
        '"example_en": "...", "example_tr": "...", "part_of_speech": "..."}]}\n\n'
        'Words:\n- ' + '\n- '.join(cleaned)
    )
    data = _chat_json(system, user)
    items = data.get('items', [])
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        eng = str(it.get('english') or '').strip()
        tr = str(it.get('turkish') or '').strip()
        if not eng or not tr:
            continue
        out.append({
            'english': eng,
            'turkish': tr,
            'example_en': str(it.get('example_en') or '').strip(),
            'example_tr': str(it.get('example_tr') or '').strip(),
            'part_of_speech': str(it.get('part_of_speech') or '').strip(),
        })
    return out


def generate_topic_quiz(topic_name: str, explanation: str, example_sentences: list[str], n: int = 50) -> list[dict]:
    system = (
        f'You generate English grammar practice questions for a Turkish learner. '
        f'Topic: "{topic_name}". Mix question types: translate_tr_en (Turkish sentence to translate), '
        f'translate_en_tr (English sentence to translate), fill_blank (English sentence with ___ gap, '
        f'answer is the missing word/phrase), multiple_choice (English question with 4 options, '
        f'one correct). Include positive, negative, and question forms. Keep sentences short and natural.'
    )
    examples_text = '\n'.join(f'- {s}' for s in example_sentences[:8]) if example_sentences else '(none)'
    user = (
        f'Topic explanation:\n{explanation or "(basic usage)"}\n\n'
        f'Reference examples:\n{examples_text}\n\n'
        f'Generate exactly {n} varied questions. Return JSON:\n'
        '{"items": [{"question_type": "translate_tr_en|translate_en_tr|fill_blank|multiple_choice", '
        '"prompt": "...", "correct_answer": "...", "choices": ["...","...","...","..."] or null}]}\n\n'
        'STRICT rules for multiple_choice:\n'
        '- "prompt" contains ONLY the question. Do NOT embed the options (no "A) ..." inside the prompt).\n'
        '- "choices" is an array of exactly 4 non-empty strings, each the full option text.\n'
        '- Do NOT prefix choices with letters like "A." / "B)".\n'
        '- "correct_answer" MUST be the verbatim full text of one of the choices (not "A"/"B"/etc.).\n'
        'For other question types, "choices" must be null and "correct_answer" is the expected answer text.'
    )
    data = _chat_json(system, user)
    return data.get('items', [])


def generate_word_quiz_extras(words: list[dict], n: int = 50) -> list[dict]:
    """
    Given a list of words ({english, turkish}), produce n quiz items.
    We ask AI to mix simple translations and a few multiple-choice questions using distractors.
    """
    if not words:
        return []
    system = (
        'You build vocabulary quizzes for a Turkish learner of English. Mix translate_en_tr, '
        'translate_tr_en, and multiple_choice questions. For multiple choice, give 4 English-meaning '
        'options (or Turkish-meaning options) with one correct. Keep answers short.'
    )
    sample = words[:80]
    words_block = '\n'.join(f'- {w["english"]} = {w["turkish"]}' for w in sample)
    user = (
        f'Word pool:\n{words_block}\n\n'
        f'Create exactly {n} quiz items using ONLY words from the pool. Return JSON:\n'
        '{"items": [{"question_type": "translate_en_tr|translate_tr_en|multiple_choice", '
        '"prompt": "...", "correct_answer": "...", "english_word": "the pool word used", '
        '"choices": ["...", "...", "...", "..."] or null}]}\n\n'
        'STRICT rules for multiple_choice:\n'
        '- "choices" must be an array of exactly 4 non-empty strings — no empty items, no "A."/"B)" prefixes.\n'
        '- "correct_answer" MUST be the verbatim full text of one of the choices (never just a letter).\n'
        '- "prompt" must NOT embed the options inline.\n'
        'For other question types, "choices" must be null.'
    )
    data = _chat_json(system, user)
    return data.get('items', [])


_INTERVIEW_FIELDS = ('question_tr', 'question_en', 'answer_tr', 'answer_en')


def _clean_interview_items(items):
    if not isinstance(items, list):
        return []
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        cleaned = {k: str(it.get(k) or '').strip() for k in _INTERVIEW_FIELDS}
        if all(cleaned.values()):
            out.append(cleaned)
    return out


def generate_interview_questions(job_title: str, n: int = 10) -> list[dict]:
    system = (
        'You are an expert technical recruiter and interview coach. '
        'Generate realistic job interview questions for the given position. '
        'Each question must have: question in Turkish, question in English, '
        'a detailed answer in Turkish, and a detailed answer in English. '
        'Mix behavioral, technical, and situational questions. '
        'Every field must be non-empty. '
        'Respond ONLY in the requested JSON format.'
    )
    user = (
        f'Position: "{job_title}"\n\n'
        f'Generate exactly {n} interview questions. Return JSON:\n'
        '{"items": [{"question_tr": "...", "question_en": "...", '
        '"answer_tr": "...", "answer_en": "..."}]}\n'
        'All four fields are required for every item.'
    )
    data = _chat_json(system, user)
    return _clean_interview_items(data.get('items', []))


def generate_interview_from_cv(cv_text: str, n: int = 10) -> list[dict]:
    system = (
        'You are an expert technical recruiter and interview coach. '
        'You will receive the text content of a candidate\'s CV/resume. '
        'Analyze their skills, experience, job titles, and tech stack. '
        'Generate realistic interview questions that a recruiter would ask THIS specific candidate. '
        'Each question must have: question in Turkish, question in English, '
        'a detailed answer in Turkish, and a detailed answer in English. '
        'Focus on their actual skills and experience from the CV. '
        'Mix behavioral, technical, and situational questions. '
        'Every field must be non-empty. '
        'Respond ONLY in the requested JSON format.'
    )
    user = (
        f'CV Content:\n{cv_text[:4000]}\n\n'
        f'Generate exactly {n} personalized interview questions based on this CV. Return JSON:\n'
        '{"items": [{"question_tr": "...", "question_en": "...", '
        '"answer_tr": "...", "answer_en": "..."}]}\n'
        'All four fields are required for every item.'
    )
    data = _chat_json(system, user)
    return _clean_interview_items(data.get('items', []))


def chat(messages: list[dict]) -> str:
    system = {
        'role': 'system',
        'content': (
            'You are a friendly English tutor. Help the user practice English. '
            'When they write in Turkish, answer in both English and Turkish. '
            'When they write in English, reply in English and gently correct mistakes. '
            'Keep answers focused and not too long.'
        ),
    }
    resp = client().chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[system] + messages,
    )
    return resp.choices[0].message.content or ''
