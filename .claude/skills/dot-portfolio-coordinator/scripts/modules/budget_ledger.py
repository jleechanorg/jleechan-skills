"""Budget ledger module for dot-portfolio-coordinator.

Implements:
- Cumulative spending ceiling across retries, attempts, and agents
- Local OS principal verification against reviewed allowlist
- Strict rejection of unauthenticated JSON caller IDs
- Idempotent reservation replay
- Terminal overrun accounting (no global reservation freeze)
- Settlement of actual costs and release of unspent allocations
"""
from fractions import Fraction
import json
import math
import os
from typing import Any, Dict, List, Optional


class BudgetError(Exception):
    """Raised on budget allocation or caller authentication errors."""
    pass


class BudgetLedger:
    """Manages cumulative budget allocations, reservations, and settlements."""

    def __init__(self, registry: Any, ledger_file: Optional[str] = None):
        self.registry = registry
        self.ledger_file = ledger_file
        self.per_cycle_ceiling = float(
            registry.budget_policy.get("per_cycle_cost_usd", 0.50)
        )
        self.ledger_version = 1
        self.total_reserved = 0.0
        self.total_settled = 0.0
        self.reservations: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self.ledger_file:
            return
        try:
            with open(self.ledger_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or type(data.get("ledger_version")) is not int or data["ledger_version"] < 1:
                raise ValueError("invalid ledger version")
            reserved = self._amount(data, "total_reserved", allow_negative=True)
            settled = self._amount(data, "total_settled")
            reservations = data.get("reservations")
            if not isinstance(reservations, dict):
                raise ValueError("invalid reservations")
            expected_reserved = expected_settled = Fraction()
            reserved_volume = settled_volume = Fraction()
            reserve_operations = settlement_operations = 0
            for key, record in reservations.items():
                if not isinstance(record, dict) or record.get("reservation_id") != key:
                    raise ValueError("invalid reservation identity")
                maximum = self._amount(record, "max_cost")
                allocation = self._amount(record, "reserved_amount")
                actual = self._amount(record, "settled_amount")
                allocation = Fraction(allocation)
                actual = Fraction(actual)
                reserved_volume += allocation
                reserve_operations += 1
                status = record.get("status")
                if maximum != allocation or not isinstance(record.get("caller_principal"), str):
                    raise ValueError("invalid reservation")
                if status == "active" and actual == 0:
                    expected_reserved += allocation
                elif status == "settled" and actual <= allocation:
                    expected_settled += actual
                elif status == "overrun_blocked" and actual > allocation:
                    expected_settled += actual
                else:
                    raise ValueError("invalid reservation state")
                if status != "active":
                    reserved_volume += allocation
                    settled_volume += actual
                    reserve_operations += 1
                    settlement_operations += 1
            # Each retained record proves one reserve and at most one settlement.
            # Reject histories with missing/unrepresented accounting operations.
            if data["ledger_version"] != 1 + reserve_operations:
                raise ValueError("unsupported ledger operation history")
            reserved = self._reconcile_total(reserved, expected_reserved,
                                             reserved_volume, reserve_operations)
            settled = self._reconcile_total(settled, expected_settled,
                                            settled_volume, settlement_operations)
        except FileNotFoundError as exc:
            if self.reservations:
                raise BudgetError("Persisted budget ledger disappeared") from exc
            return
        except (OSError, ValueError, TypeError, OverflowError, BudgetError) as exc:
            raise BudgetError("Invalid or unreadable persisted budget ledger") from exc
        # Validate the complete replacement before changing any in-memory state.
        self.ledger_version = data["ledger_version"]
        self.total_reserved, self.total_settled = reserved, settled
        self.reservations = reservations

    @staticmethod
    def _reconcile_total(stored: float, exact: Fraction, volume: Fraction,
                         operations: int) -> float:
        """Compatibility envelope for binary64 add/subtract in any valid order.

        With u=2^-53, n operations and S=sum(abs(operands)), accumulated
        rounding error is at most (n*u*S + n*eta)/(1-n*u), eta=2^-1075
        allowing gradual underflow. Exact rationals avoid rounding the bound.
        Clamping at zero cannot increase error against nonnegative accounting.
        Reload reconciliation resets error to one correctly rounded exact sum.

        Records do not retain order/provenance: this is an explicit acceptance
        envelope, not proof that a particular history occurred. Corruption
        inside it is indistinguishable; outside it fails without a write.
        """
        nu = Fraction(operations, 1 << 53)
        if nu >= 1:
            raise ValueError("unsupported rounding history")
        bound = (nu * volume + Fraction(operations, 1 << 1075)) / (1 - nu)
        if abs(Fraction(stored) - exact) > bound:
            raise ValueError("inconsistent ledger total beyond accounting bound")
        result = float(exact)
        if not math.isfinite(result):
            raise ValueError("unrepresentable ledger total")
        return result

    def _save(self) -> None:
        if self.ledger_file:
            os.makedirs(os.path.dirname(os.path.abspath(self.ledger_file)), exist_ok=True)
            data = {
                "ledger_version": self.ledger_version,
                "total_reserved": self.total_reserved,
                "total_settled": self.total_settled,
                "reservations": self.reservations
            }
            tmp = f"{self.ledger_file}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, self.ledger_file)

    def _verify_caller(self, caller_os_principal: str) -> None:
        if not caller_os_principal or caller_os_principal not in self.registry.caller_allowlist:
            raise BudgetError(
                f"Unauthorized caller principal: '{caller_os_principal}'. "
                "Must be a reviewed principal in caller_allowlist. "
                "JSON caller field is not accepted as authentication."
            )

    @staticmethod
    def _amount(request: Dict[str, Any], field: str, *, allow_negative: bool = False) -> float:
        """Require a finite JSON number; negativity is allowed only for load reconciliation."""
        value = request.get(field)
        if type(value) not in (int, float):
            raise BudgetError(f"{field} must be a finite nonnegative JSON number")
        try:
            amount = float(value)
        except OverflowError:
            raise BudgetError(f"{field} exceeds the supported numeric range") from None
        if not math.isfinite(amount) or (amount < 0 and not allow_negative):
            raise BudgetError(f"{field} must be a finite nonnegative JSON number")
        return amount

    @property
    def remaining_ceiling(self) -> float:
        rem = self.per_cycle_ceiling - self.total_reserved - self.total_settled
        return round(max(0.0, rem), 4)

    def reserve(self, request: Dict[str, Any], caller_os_principal: str) -> Dict[str, Any]:
        """Atomically reserves budget for a contemplated execution attempt."""
        self._verify_caller(caller_os_principal)

        action_id = request.get("action_id", "")
        attempt_id = request.get("attempt_id", "")
        max_cost = self._amount(request, "max_cost")
        self._load()
        res_id = f"res_{action_id}_{attempt_id}"

        # Idempotence check
        if res_id in self.reservations:
            existing = self.reservations[res_id]
            if existing["max_cost"] == max_cost:
                return {
                    "status": "reserved",
                    "ledger_version": self.ledger_version,
                    "reservation_id": res_id,
                    "accepted_amount": max_cost,
                    "remaining_ceiling": self.remaining_ceiling
                }
            raise BudgetError(f"Conflicting limits for existing reservation {res_id}")

        # Check capacity
        if max_cost > self.remaining_ceiling:
            return {
                "status": "rejected",
                "ledger_version": self.ledger_version,
                "reservation_id": res_id,
                "accepted_amount": 0.0,
                "remaining_ceiling": self.remaining_ceiling,
                "reason": f"Requested cost {max_cost} exceeds remaining ceiling {self.remaining_ceiling}"
            }

        self.total_reserved += max_cost
        self.ledger_version += 1
        self.reservations[res_id] = {
            "reservation_id": res_id,
            "caller_principal": caller_os_principal,
            "max_cost": max_cost,
            "reserved_amount": max_cost,
            "settled_amount": 0.0,
            "status": "active",
            "task_key": request.get("task_key"),
            "grant_version": request.get("grant_version")
        }
        self._save()

        return {
            "status": "reserved",
            "ledger_version": self.ledger_version,
            "reservation_id": res_id,
            "accepted_amount": max_cost,
            "remaining_ceiling": self.remaining_ceiling
        }

    def settle(self, request: Dict[str, Any], caller_os_principal: str) -> Dict[str, Any]:
        """Settles an active reservation with actual verified spend."""
        self._verify_caller(caller_os_principal)

        res_id = request.get("reservation_id", "")
        actual_cost = self._amount(request, "actual_cost")
        self._load()

        if res_id not in self.reservations:
            return {
                "status": "rejected",
                "ledger_version": self.ledger_version,
                "reservation_id": res_id,
                "settled_amount": 0.0,
                "remaining_ceiling": self.remaining_ceiling,
                "reason": f"Reservation {res_id} not found"
            }

        res = self.reservations[res_id]
        if res["status"] in ("settled", "overrun_blocked"):
            # Replay protection: return existing result
            if res["settled_amount"] == actual_cost:
                return {
                    "status": res["status"],
                    "ledger_version": self.ledger_version,
                    "reservation_id": res_id,
                    "settled_amount": actual_cost,
                    "remaining_ceiling": self.remaining_ceiling
                }
            raise BudgetError(f"Conflicting settlement amount for already settled reservation {res_id}")

        reserved_amt = res["reserved_amount"]

        # Mark this reservation terminal; this does not globally freeze reservations.
        if actual_cost > reserved_amt:
            self.total_reserved = max(0.0, self.total_reserved - reserved_amt)
            self.total_settled += actual_cost
            self.ledger_version += 1
            res["status"] = "overrun_blocked"
            res["settled_amount"] = actual_cost
            self._save()
            return {
                "status": "overrun_blocked",
                "ledger_version": self.ledger_version,
                "reservation_id": res_id,
                "settled_amount": actual_cost,
                "remaining_ceiling": self.remaining_ceiling,
                "reason": f"Actual cost {actual_cost} exceeds reserved {reserved_amt}"
            }

        # Normal settlement
        self.total_reserved = max(0.0, self.total_reserved - reserved_amt)
        self.total_settled += actual_cost
        self.ledger_version += 1
        res["status"] = "settled"
        res["settled_amount"] = actual_cost
        self._save()

        return {
            "status": "settled",
            "ledger_version": self.ledger_version,
            "reservation_id": res_id,
            "settled_amount": actual_cost,
            "remaining_ceiling": self.remaining_ceiling
        }

    def status(self, reservation_id: str, caller_os_principal: str) -> Dict[str, Any]:
        """Queries the status of a specific reservation."""
        self._verify_caller(caller_os_principal)

        if reservation_id not in self.reservations:
            return {
                "status": "unknown_reservation",
                "ledger_version": self.ledger_version,
                "reservation_id": reservation_id,
                "reserved_amount": 0.0,
                "settled_amount": 0.0,
                "remaining_ceiling": self.remaining_ceiling
            }

        res = self.reservations[reservation_id]
        return {
            "status": res["status"],
            "ledger_version": self.ledger_version,
            "reservation_id": reservation_id,
            "reserved_amount": res["reserved_amount"],
            "settled_amount": res["settled_amount"],
            "remaining_ceiling": self.remaining_ceiling
        }
