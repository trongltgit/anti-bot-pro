import time

from app.customer.repository import (
    CustomerAPIRepository,
    CustomerAPIError,
    CustomerAPIUnavailable,
    CustomerAPITimeout,
)


class CustomerNotFound(Exception):
    pass


class CustomerInactive(Exception):
    pass


class CustomerAccessDenied(Exception):
    pass


class CustomerService:

    def __init__(self, repository=None):
        self.repository = (
            repository
            or CustomerAPIRepository()
        )

    def get_customer(self, customer_id):
        customer = self.repository.get_customer(
            customer_id
        )

        if not customer:
            raise CustomerNotFound(
                "Không tìm thấy khách hàng."
            )

        status = customer.get("status", "").upper()

        if status not in {
            "ACTIVE",
            "ACTIVATED",
            "OPEN"
        }:
            raise CustomerInactive(
                "Khách hàng không ở trạng thái hoạt động."
            )

        return customer

    def get_customer_by_cif(self, cif):
        customer = self.repository.get_customer_by_cif(cif)

        if not customer:
            raise CustomerNotFound(
                "Không tìm thấy CIF."
            )

        status = customer.get("status", "").upper()

        if status not in {
            "ACTIVE",
            "ACTIVATED",
            "OPEN"
        }:
            raise CustomerInactive(
                "Khách hàng không ở trạng thái hoạt động."
            )

        return customer

    def check_currency_permission(
        self,
        customer,
        currency
    ):
        permissions = customer.get(
            "currency_permissions"
        ) or []

        # Nếu Customer API không cung cấp danh sách,
        # không tự động từ chối ở tầng adapter.
        if not permissions:
            return True

        normalized = {
            str(item).upper()
            for item in permissions
        }

        return currency.upper() in normalized

    def check_amount_limit(
        self,
        customer,
        amount
    ):
        daily_limit = customer.get("daily_limit")

        if daily_limit is None:
            return True

        try:
            return float(amount) <= float(daily_limit)
        except (TypeError, ValueError):
            return False
