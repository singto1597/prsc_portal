"""
📡 Request Context — เก็บข้อมูลของ HTTP request ปัจจุบัน (contextvar)

ใช้ให้ AuditLogger เก็บ ip_address / user_agent / trace_id อัตโนมัติโดยไม่ต้อง
แก้ signature ของ service ทุกตัว:
- middleware ใน main.py ตั้ง context ตอนรับ request → services/logger อ่านได้
- พอ request จบ → clear (กัน leak ข้าม request)
- worker/background job ที่ไม่ได้ผ่าน HTTP → context ว่าง → ค่า None
"""
from contextvars import ContextVar
from typing import Dict, Optional

_AUDIT_CTX: ContextVar[Dict] = ContextVar("audit_ctx", default={})


def set_audit_context(
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> None:
    """ตั้ง context ของ request ปัจจุบัน (เรียกจาก middleware)"""
    _AUDIT_CTX.set({
        "ip_address": ip_address,
        "user_agent": user_agent,
        "trace_id": trace_id,
    })


def get_audit_context() -> Dict:
    """อ่าน context ปัจจุบัน (ค่า default = {} ถ้ายังไม่ตั้ง)"""
    return _AUDIT_CTX.get()


def clear_audit_context() -> None:
    """ล้าง context (เรียกหลัง request จบ — กัน leak ข้าม request)"""
    _AUDIT_CTX.set({})
