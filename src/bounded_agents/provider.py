"""Budgeted adapter over the existing OpenAI structured-provider stack.

No hidden retries/tools/history; exact input preflight and server output cap.
Unknown upstream outcomes retain their full spend/token reservation.
"""
from decimal import Decimal
import json
from threading import Event, Lock
import time

from openai.lib._parsing._responses import type_to_text_format_param

from src.llm.base import ProviderConfigurationError, ProviderMalformedOutputError
from src.llm.openai_provider import (OpenAIStructuredProvider, _OpenAISynthesisDraft,
    _to_governed_draft)
from src.orchestration.models import ProviderResult, SynthesisDraft, TokenUsage
from .models import AgentBudgetState
from .diagnostics import failure_category


class ProviderBudgetExceeded(RuntimeError):
    pass


class SpendLedger:
    """Shared across both modes/cases; no refund for ambiguous failed requests."""
    def __init__(self, max_usd):
        self.max_usd = Decimal(str(max_usd))
        if not self.max_usd.is_finite() or self.max_usd <= 0:
            raise ValueError("Explicit positive total spending cap required")
        self.committed_usd = Decimal("0")
        self.blocked = False
        self.lock = Lock()

    def reserve(self, cost):
        with self.lock:
            if self.blocked or self.committed_usd + cost > self.max_usd:
                raise ProviderBudgetExceeded("Total evaluation spending cap")
            self.committed_usd += cost

    def settle(self, reserved, actual):
        if actual > reserved:
            self.blocked = True
            raise ProviderBudgetExceeded("Provider usage exceeded reservation")
        with self.lock:
            self.committed_usd -= reserved - actual


class BudgetedOpenAIProvider(OpenAIStructuredProvider):
    """Opt-in only; original provider and v1 graph implementation stay intact."""
    def __init__(self, *, model, input_rate, output_rate, ledger, limits=None, client=None):
        if not model:
            raise ProviderConfigurationError("Explicit evaluation model required")
        self.input_rate = Decimal(str(input_rate))
        self.output_rate = Decimal(str(output_rate))
        if any(not rate.is_finite() or rate <= 0 for rate in (self.input_rate, self.output_rate)):
            raise ProviderConfigurationError("Verified positive per-million pricing required")
        if client is None:
            super().__init__(model=model, max_retries=0,
                input_cost_per_million=self.input_rate, output_cost_per_million=self.output_rate)
        else:
            self.client = client
            self.model = model
        self.ledger = ledger
        self.limits = limits or AgentBudgetState()
        self.calls = 0
        self.role_calls = {}
        self.committed_tokens = 0
        self.deadline = None
        self.records = []
        self.failures = []
        self.preflights = []
        self.lock = Lock()
        self.cancelled = Event()

    def cancel_pending(self):
        """Cooperative stop only; does NOT cancel an active synchronous socket.

        Unknown requests keep reservations. No background response is released.
        A truly cancellable transport is required before concurrent branches.
        """
        self.cancelled.set()

    def can_reserve_calls(self, count, limits):
        """Read-only conservative admission; actual preflight still reserves.

        Counts future maximum-sized calls, including downstream work. This does
        not refund unknown requests or spend money. Serial runtime only.
        """
        worst = (min(limits.max_input_tokens_per_call, self.limits.max_input_tokens_per_call)*self.input_rate
            + min(limits.max_output_tokens_per_call, self.limits.max_output_tokens_per_call)*self.output_rate) / Decimal(1000000)
        with self.ledger.lock:
            return not self.cancelled.is_set() and not self.ledger.blocked and self.ledger.committed_usd + count*worst <= self.ledger.max_usd

    def _check_active(self, deadline):
        if self.cancelled.is_set():
            raise TimeoutError("Request cancelled")
        if time.monotonic() >= deadline:
            raise ProviderBudgetExceeded("Provider deadline")

    def generate_structured(self, **kwargs):
        return self.generate_bounded(limits=self.limits, deadline=None, **kwargs)

    def generate_bounded(self, *, limits, deadline, role, prompt, payload,
                         output_model, prompt_version, revision=False):
        record_count = len(self.records)
        started = time.monotonic()
        try:
            return self._generate_bounded(limits=limits, deadline=deadline, role=role,
                prompt=prompt, payload=payload, output_model=output_model,
                prompt_version=prompt_version, revision=revision)
        except Exception as error:
            detail = {"role":role, "error_category":failure_category(error).value,
                "error_type":type(error).__name__, "duration_ms":(time.monotonic()-started)*1000,
                "revision":revision}
            self.failures.append(detail)
            if len(self.records) > record_count:
                self.records[-1].update(detail)
            raise

    def _generate_bounded(self, *, limits, deadline, role, prompt, payload,
                          output_model, prompt_version, revision=False):
        now = time.monotonic()
        if self.deadline is None:
            self.deadline = now + self.limits.max_seconds
        deadline = min(deadline or self.deadline, self.deadline)
        group = role.split(".")[0]
        with self.lock:
            if self.calls >= min(limits.max_total_calls, self.limits.max_total_calls) or self.role_calls.get(group, 0) >= min(limits.max_calls_per_role, self.limits.max_calls_per_role):
                raise ProviderBudgetExceeded("Provider call limit")
            self._check_active(deadline)
            self.calls += 1
            self.role_calls[group] = self.role_calls.get(group, 0) + 1
        wire_model = _OpenAISynthesisDraft if output_model is SynthesisDraft else output_model
        def serialize(value):
            if hasattr(value, "model_dump"):
                return value.model_dump(mode="json")
            raise TypeError("Unsupported structured payload")
        messages = [{"role":"system", "content":prompt},
            {"role":"user", "content":json.dumps(payload, default=serialize, sort_keys=True)}]
        # Match the SDK's strict schema for input counting and generation.
        text_format = {"format": type_to_text_format_param(wire_model)}
        self._check_active(deadline)
        client = self.client.with_options(max_retries=0, timeout=max(.001, deadline-time.monotonic()))
        preflight = {"role":role, "revision":revision, "status":"running",
            "payload_bytes":len(messages[1]["content"].encode()),
            "remaining_ms":max(0, deadline-time.monotonic())*1000}
        self.preflights.append(preflight)
        count_started = time.monotonic()
        try:
            counted = client.responses.input_tokens.count(model=self.model, input=messages,
                text=text_format, truncation="disabled")
            preflight["status"] = "completed"
        except Exception:
            preflight["status"] = "failed"
            raise
        finally:
            preflight["duration_ms"] = (time.monotonic()-count_started)*1000
        self._check_active(deadline)
        input_tokens = counted.input_tokens
        if not isinstance(input_tokens, int) or isinstance(input_tokens, bool) or input_tokens < 0:
            raise ProviderMalformedOutputError("Invalid preflight token count")
        if input_tokens > min(limits.max_input_tokens_per_call, self.limits.max_input_tokens_per_call):
            raise ProviderBudgetExceeded("Input token limit")
        with self.lock:
            remaining = min(limits.max_tokens, self.limits.max_tokens) - self.committed_tokens - input_tokens
            output_cap = min(limits.max_output_tokens_per_call, self.limits.max_output_tokens_per_call, remaining)
            if output_cap <= 0 or time.monotonic() >= deadline:
                raise ProviderBudgetExceeded("Provider token/deadline limit")
            reserved_tokens = input_tokens + output_cap
            reserved_cost = (input_tokens*self.input_rate + output_cap*self.output_rate) / Decimal(1000000)
            self.ledger.reserve(reserved_cost)
            self.committed_tokens += reserved_tokens
        record = {"role":role, "input_tokens_counted":input_tokens, "output_cap":output_cap,
            "reserved_usd":str(reserved_cost), "status":"unknown", "revision":revision,
            "preflight_ms":preflight["duration_ms"], "payload_bytes":preflight["payload_bytes"],
            "remaining_ms":max(0, deadline-time.monotonic())*1000}
        self.records.append(record)
        # Explicit HTTP timeout, output cap, no SDK retries or provider tools.
        # Closing the socket cannot guarantee cancellation of upstream computation.
        client = self.client.with_options(max_retries=0, timeout=max(.001, deadline-time.monotonic()))
        kwargs = dict(model=self.model, input=messages, max_output_tokens=output_cap,
            store=False, truncation="disabled", service_tier="default")
        # Critic schema validators must run AFTER usage is accounted, so a
        # semantic/schema failure cannot erase a confirmed paid response.
        generation_started = time.monotonic()
        try:
            self._check_active(deadline)
            response = client.responses.create(text=text_format, **kwargs) if role == "critic" else client.responses.parse(text_format=wire_model, **kwargs)
        finally:
            record["generation_ms"] = (time.monotonic()-generation_started)*1000
        usage = response.usage
        if usage is None or any(not isinstance(x, int) or isinstance(x, bool) or x < 0
            for x in (usage.input_tokens, usage.output_tokens)):
            raise ProviderMalformedOutputError("Missing/invalid usage; reservation retained")
        if usage.input_tokens > input_tokens or usage.output_tokens > output_cap:
            self.ledger.blocked = True
            raise ProviderBudgetExceeded("Provider usage violated counted/capped request")
        actual_cost = (usage.input_tokens*self.input_rate + usage.output_tokens*self.output_rate) / Decimal(1000000)
        self.ledger.settle(reserved_cost, actual_cost)
        with self.lock:
            self.committed_tokens -= reserved_tokens - usage.input_tokens - usage.output_tokens
        record.update(status="completed", input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens, actual_usd=str(actual_cost))
        self._check_active(deadline)
        if response.status != "completed":
            raise ProviderMalformedOutputError("Incomplete structured response")
        if role == "critic":
            if not response.output_text:
                raise ProviderMalformedOutputError("Empty critic output")
            parsed = output_model.model_validate_json(response.output_text)
        else:
            if response.output_parsed is None:
                raise ProviderMalformedOutputError("Empty structured output")
            parsed = _to_governed_draft(response.output_parsed) if output_model is SynthesisDraft else output_model.model_validate_json(response.output_parsed.model_dump_json())
        return ProviderResult(value=parsed, usage=TokenUsage(input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens, estimated_cost_usd=actual_cost),
            provider_name=self.name, provider_model=self.model, prompt_version=prompt_version)
