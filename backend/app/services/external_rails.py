"""Sandbox-only integration contracts. No live rail is implemented or selectable.
An explicit idempotency key and persisted intent precede submission. Provider calls
are a separate concern: a provider crash must not turn into a fictional payment.
"""
from typing import Protocol
from dataclasses import dataclass

@dataclass(frozen=True)
class RailRequest:
    idempotency_key: str
    kind: str
    amount_paise: int
    currency: str = 'INR'

class EscrowProvider(Protocol):
    def reserve(self, request: RailRequest) -> dict: ...

class InsurerProvider(Protocol):
    def submit_claim(self, request: RailRequest) -> dict: ...

class DryRunProvider:
    def reserve(self, request: RailRequest) -> dict:
        if request.amount_paise<=0 or request.currency!='INR':raise ValueError('Invalid amount/currency')
        return {'status':'dry_run_only','mode':'sandbox','idempotency_key':request.idempotency_key,
                'actual_money_moved':False,'provider_connected':False}
    def submit_claim(self, request: RailRequest) -> dict:return self.reserve(request)
