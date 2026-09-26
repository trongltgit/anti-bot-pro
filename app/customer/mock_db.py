"""
Mock Customer DB + Users (Demo)
===============================

Roles:
  HQ        – Hội sở (TSC): thấy hết; margin CN chỉ sau deal done
  CN_ADMIN  – Admin chi nhánh: gán CIF cho nhân viên, xem log CN
  PNV       – Nhân viên CN: chỉ CIF được gán; multi-quote
  CUSTOMER  – Khách hàng: chỉ giá điều hòa (TGDH); CIF phải online
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
        "online": True,
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
        "online": True,
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
        "online": False,
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
        "online": False,
        "daily_limit": 100000,
        "monthly_limit": 1000000,
        "currency_permissions": ["USD"],
    },
}


DEMO_BRANCHES = {
    "CN001": {
        "branch_id": "CN001",
        "branch_name": "Chi nhanh Quan 1",
        "customer_ids": ["CUST001", "CUST003"],
    },
    "CN002": {
        "branch_id": "CN002",
        "branch_name": "Chi nhanh Quan 3",
        "customer_ids": ["CUST002"],
    },
}

DEMO_USERS = {
    # === HỘI SỞ (TSC) ===
    "hq01": {
        "user_id": "hq01",
        "password": "demo123",
        "role": "HQ",
        "name": "Quan tri Hoi so",
        "permitted_customers": ["CUST001", "CUST002", "CUST003"],
        "branch_ids": ["CN001", "CN002"],
    },
    # === ADMIN CHI NHÁNH ===
    "admin_cn01": {
        "user_id": "admin_cn01",
        "password": "demo123",
        "role": "CN_ADMIN",
        "name": "Admin CN Quan 1",
        "branch_id": "CN001",
        "permitted_customers": ["CUST001", "CUST003"],
    },
    # === NHÂN VIÊN CN ===
    "staff01": {
        "user_id": "staff01",
        "password": "demo123",
        "role": "PNV",
        "name": "Nhan vien CN A",
        "branch_id": "CN001",
        "permitted_customers": ["CUST001", "CUST003"],
    },
    "staff02": {
        "user_id": "staff02",
        "password": "demo123",
        "role": "PNV",
        "name": "Nhan vien CN B",
        "branch_id": "CN002",
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
    cif = str(cif or "").strip()
    for c in DEMO_CUSTOMERS.values():
        if str(c.get("cif", "")).strip() == cif:
            return deepcopy(c)
    return None


def list_demo_customers():
    return [deepcopy(c) for c in DEMO_CUSTOMERS.values()]


def list_demo_customers_by_ids(ids):
    out = []
    for c in DEMO_CUSTOMERS.values():
        if c["customer_id"] in (ids or []):
            out.append(deepcopy(c))
    return out


def list_active_customers():
    return [deepcopy(c) for c in DEMO_CUSTOMERS.values() if c["status"] == "ACTIVE"]


def get_demo_user(username: str):
    user = DEMO_USERS.get(username)
    if not user:
        return None
    return deepcopy(user)


def list_demo_branches():
    return [deepcopy(b) for b in DEMO_BRANCHES.values()]


def get_demo_branch(branch_id: str):
    b = DEMO_BRANCHES.get(branch_id)
    if not b:
        return None
    return deepcopy(b)


def assign_cif_to_staff(admin_user_id: str, staff_user_id: str, customer_ids: list):
    """CN_ADMIN gán CIF cho nhân viên."""
    admin = DEMO_USERS.get(admin_user_id)
    staff = DEMO_USERS.get(staff_user_id)
    if not admin or admin.get("role") != "CN_ADMIN":
        return False, "Chỉ Admin CN được gán CIF."
    if not staff or staff.get("role") not in {"PNV", "STAFF"}:
        return False, "User không phải nhân viên CN."
    if admin.get("branch_id") != staff.get("branch_id"):
        return False, "Khác chi nhánh."
    branch = DEMO_BRANCHES.get(admin.get("branch_id") or "")
    allowed = set((branch or {}).get("customer_ids") or [])
    for cid in customer_ids:
        if cid not in allowed:
            return False, f"CIF {cid} không thuộc chi nhánh."
    staff["permitted_customers"] = list(customer_ids)
    return True, "OK"


def set_customer_online(customer_id: str, online: bool, actor_role: str, branch_id: str = ""):
    c = DEMO_CUSTOMERS.get(customer_id)
    if not c:
        return False, "Không tìm thấy CIF."
    if actor_role not in {"CN_ADMIN", "PNV", "STAFF", "HQ"}:
        return False, "Không có quyền."
    if actor_role != "HQ" and branch_id:
        branch = DEMO_BRANCHES.get(branch_id)
        if not branch or customer_id not in branch.get("customer_ids", []):
            return False, "CIF không thuộc chi nhánh."
    c["online"] = bool(online)
    return True, "OK"


def authenticate_demo_user(username: str, password: str):
    user = DEMO_USERS.get(username)
    if not user:
        return None
    if user.get("password") != password:
        return None
    return deepcopy(user)


def customers_of_branch(branch_id: str):
    b = DEMO_BRANCHES.get(branch_id)
    if not b:
        return []
    return list_demo_customers_by_ids(b.get("customer_ids") or [])
