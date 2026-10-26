"""Bounded intent hints from already-authorized text; never a data permission."""
import re
import unicodedata
from typing import Literal

Intent = Literal['conversation', 'listening', 'support', 'practical', 'reflection', 'activity', 'connection', 'analysis']
CONVERSATION_POLICY = 'conversation-intent-v1'


def current_text(history: list[dict]) -> str:
    # The provider receives only F03's projection. Do not inspect saved messages,
    # approved-memory text, assistant prose or a discarded history prefix here.
    latest = history[-1].get('content', '') if history and history[-1].get('role') == 'user' else ''
    if not isinstance(latest, str):
        latest = ''
    return ''.join(c for c in unicodedata.normalize('NFD', latest.lower().replace('đ', 'd'))
                   if not unicodedata.combining(c))


def requested_presentation(history: list[dict]) -> tuple[bool, bool]:
    text = current_text(history)
    brief = bool(re.search(r'\b(?:ngan|gon)\b|mot cau|khong lap|dung lap', text))
    omit_mean = bool(re.search(r'(?:dung|khong (?:can|muon)).{0,30}trung binh', text))
    return brief, omit_mean


def conversation_intent(bot_id: str, history: list[dict], *, scoped: bool) -> Intent:
    text = current_text(history)
    negative_analysis = r'(dung|khong(?: (?:muon|can))?|thoi khong) (?:ban )?(?:(?:xem|doc) (?:hay |va |hoac )?)?(?:phan tich|thong ke|so sanh)(?! (?:dai|lau|qua sau|chi tiet))'
    opt_out = bool(re.search(negative_analysis, text))
    request_text = re.sub(negative_analysis, '', text)
    if re.search(r'phan tich|so sanh|tinh (?:diem|trung binh)|thong ke|trung binh|bieu do|xu huong|'
                 r'(?:nhan xet|mo ta).{0,50}(?:tam trang|diem|ban ghi|tuan|du lieu)|(?:ban ghi|diem tam trang).{0,40}(?:nao|bao nhieu)', request_text):
        return 'analysis'
    if opt_out or re.search(r'chi.{0,35}(?:lang nghe|ngoi yen)|cu.{0,20}(?:ngoi cung|o day)', text):
        return 'listening'
    if re.search(r'noi chuyen|tro chuyen|chia vui|chuyen (?:dua|vui)|cau (?:hai|dua)|ke.{0,20}(?:chuyen|truyen)|cuoi.{0,15}(?:chut|ti)|tam su', text):
        return 'conversation'
    if re.search(r'chi (?:minh|toi|cach)|cach (?:gap|lam|viet|sap xep)|meo.{0,20}(?:nao|gi)|'
                 r'bao lau|tinh.{0,15}(?:cong|tru)|giai thich.{0,25}(?:tu|cach)', text):
        return 'practical'
    if re.search(r'minh.{0,25}(?:met qua|buon qua|lo qua)|(?:vuot qua|an ui|dong vien)', text):
        return 'support'
    if bot_id == 'nhip' and scoped:
        return 'analysis'  # Ambiguity preserves the proven P0 path.
    defaults: dict[str, Intent] = {'guong':'reflection','rure':'activity','caunoi':'connection'}
    return defaults.get(bot_id, 'conversation')
