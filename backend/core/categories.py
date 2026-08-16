"""
หมวดหมู่การรับแจ้งเรื่อง — 3 หมวดหลัก แต่ละหมวดมีหัวข้อย่อย (subcategory)

อ่านจาก config/categories.json ครั้งเดียวแล้วแคช (เหมือน pattern ของ core/rbac)
ใช้ทั้งใน service (validate ตอน create_issue) และ dashboard (label)
"""
import json
import os

# แคช config
_CATEGORIES_CACHE = None


def _load_categories() -> dict:
    """โหลด config/categories.json (แคชครั้งแรก)"""
    global _CATEGORIES_CACHE
    if _CATEGORIES_CACHE is not None:
        return _CATEGORIES_CACHE

    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config", "categories.json"
    )
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        _CATEGORIES_CACHE = data.get("main_categories", {})
    except Exception:
        _CATEGORIES_CACHE = {}
    return _CATEGORIES_CACHE


def get_main_categories() -> dict:
    """คืน dict หมวดหลักทั้งหมด {code: {label, subcategories, subcategory_details}}"""
    return _load_categories()


def get_main_category_label(code: str) -> str:
    """label ภาษาไทยของหมวดหลัก"""
    return _load_categories().get(code, {}).get("label", code)


def get_subcategory_label(main_category: str, category: str) -> str:
    """label ภาษาไทยของหัวข้อย่อย"""
    main = _load_categories().get(main_category, {})
    return main.get("subcategories", {}).get(category, category)


def get_subcategory_details(main_category: str, category: str) -> str:
    """คำอธิบายของหัวข้อย่อย (สำหรับ tooltip/placeholder)"""
    main = _load_categories().get(main_category, {})
    return main.get("subcategory_details", {}).get(category, "")


def get_subcategories(main_category: str) -> dict:
    """คืน dict หัวข้อย่อยของหมวดหลัก {code: label}"""
    return _load_categories().get(main_category, {}).get("subcategories", {})


def is_valid_category(main_category: str, category: str) -> bool:
    """ตรวจว่าหมวดย่อยเป็นของหมวดหลักจริงหรือไม่"""
    return category in get_subcategories(main_category)


def all_main_category_codes() -> list:
    """รหัสหมวดหลักทั้งหมด (suggestion / wellbeing / report)"""
    return list(_load_categories().keys())


def all_subcategory_codes() -> list:
    """รหัสหมวดย่อยทั้งหมด (ข้ามหมวดหลัก)"""
    codes = []
    for main in _load_categories().values():
        codes.extend(main.get("subcategories", {}).keys())
    return codes
