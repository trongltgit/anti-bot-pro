"""
Mock Customer DB + Users (Demo)
===============================

Roles:
  HQ       – Hội sở: quản lý chính sách giá cấp 1 (chỉ HQ thấy/sửa)
  PNV      – Chi nhánh: nhập margin, xem market + final price (không thấy HQ policy)
  CUSTOMER – Khách hàng: chỉ thấy final price
"""

from copy import deepcopy

DEMO_CUSTOMERS = {
    "CUST001": {
        "customer_id": "CUST001",
        "cif": "0001234567",
        "customer_name": "Nguyen Van A",
        "segment": "VIP",
        "status": "ACTIVE",
        "pricing_tier": "GOLD",
        "daily_limit": 5000000,
        "monthly_limit": 50000000,
        "currency_permissions": ["USD", "EUR", "GBP", "JPY", "AUD", "SGD"],
    },
    "CUST002": {
        "customer_id": "CUST002",
        "cif": "0002345678",
        "customer_name": "Cong ty ABC",
        "segment": "CORPORATE",
        "status": "ACTIVE",
        "pricing_tier": "SILVER",
        "daily_limit": 2000000,
        "monthly_limit": 20000000,
        "currency_permissions": ["USD", "EUR", "SGD"],
    },
    "CUST003": {
        "customer_id": "CUST003",
        "cif": "0003456789",
        "customer_name": "Tran Thi B",
        "segment": "STANDARD",
        "status": "ACTIVE",
        "pricing_tier": "BRONZE",
        "daily_limit": 500000,
        "monthly_limit": 5000000,
        "currency_permissions": ["USD", "EUR"],
    },
    "CUST004": {
        "customer_id": "CUST004",
        "cif": "0004567890",
        "customer_name": "Inactive Customer",
        "segment": "STANDARD",
        "status": "INACTIVE",
        "pricing_tier": "BRONZE",
        "daily_limit": 100000,
        "monthly_limit": 1000000,
        "currency_permissions": ["USD"],
    },
}

DEMO_USERS = {
    # === HỘI SỞ ===
    "hq01": {
        "user_id": "hq01",
        "password": "demo123",
        "role": "HQ",
        "name": "Quan tri Hoi so",
        "permitted_customers": ["CUST001", "CUST002", "CUST003"],
    },
    # === CHI NHÁNH (Người bán) ===
    "staff01": {
        "user_id": "staff01",
        "password": "demo123",
        "role": "PNV",
        "name": "Nhan vien CN A",
        "permitted_customers": ["CUST001", "CUST002", "CUST003"],
    },
    "staff02": {
        "user_id": "staff02",
        "password": "demo123",
        "role": "PNV",
        "name": "Nhan vien CN B",
        "permitted_customers": ["CUST002"],
    },
    # === KHÁCH HÀNG ===
    "cust001": {
        "user_id": "cust001",
        "password": "demo123",
        "role": "CUSTOMER",
        "name": "Nguyen Van A",
        "customer_id": "CUST001",
        "permitted_customers": ["CUST001"],
    },
}


def get_demo_customer(customer_id: str):
    data = DEMO_CUSTOMERS.get(customer_id)
    if not data:
        return None
    return deepcopy(data)


def get_demo_customer_by_cif(cif: str):
    for c in DEMO_CUSTOMERS.values():
        if c.get("cif") == cif:
            return deepcopy(c)
    return None


def list_demo_customers():
    return [deepcopy(c) for c in DEMO_CUSTOMERS.values() if c["status"] == "ACTIVE"]


def authenticate_demo_user(username: str, password: str):
    user = DEMO_USERS.get(username)
    if not user:
        return None
    if user.get("password") != password:
        return None
    safe = {k: v for k, v in user.items() if k != "password"}
    return deepcopy(safe)
