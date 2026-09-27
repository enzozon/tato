from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from time import monotonic, sleep

from pydantic import BaseModel, ValidationError

from app.llm import Attempt, Generation, LLMProvider, LLMUnavailable, ProviderError


@dataclass(frozen=True)
class Routed[T: BaseModel]:
    value: T
    attempts: tuple[Attempt, ...]
    cached: bool = False


class Router:
    def __init__(self, providers: list[LLMProvider]):
        order = {"groq": 0, "gemini": 1, "openrouter": 2}
        if len({p.name for p in providers}) != len(providers):
            raise ValueError("Configure no máximo um modelo por provedor.")
        self.providers = sorted(providers, key=lambda provider: order[provider.name])
        self.blocked_until: dict[str, float] = {}
        self.lock = Lock()

    def generate[T: BaseModel](
        self, request: Generation, output: type[T], guard: Callable[[T], bool]
    ) -> Routed[T]:
        if request.classification == "personal":
            raise LLMUnavailable("Dados pessoais ainda não habilitados para provedores.")
        attempts: list[Attempt] = []
        # ponytail: serializa por processo; limites compartilhados antes de escalar.
        with self.lock:
            for provider in self.providers:
                if self.blocked_until.get(provider.name, 0) > monotonic():
                    attempts.append(Attempt(provider.name, "circuit_open"))
                    continue
                for retry in range(2):
                    started = monotonic()
                    try:
                        result = provider.generate(request, output.model_json_schema())
                    except ProviderError as error:
                        attempts.append(
                            Attempt(
                                provider.name,
                                "error",
                                elapsed_ms=int((monotonic() - started) * 1000),
                            )
                        )
                        if error.retryable and retry == 0:
                            sleep(0.25 * 2**retry)
                            continue
                        self.blocked_until[provider.name] = monotonic() + error.cooldown
                        break
                    valid = False
                    try:
                        value = output.model_validate_json(result.content, strict=True)
                        valid = guard(value)
                    except (ValidationError, ValueError):
                        pass
                    attempts.append(
                        Attempt(
                            provider.name,
                            "ok" if valid else "invalid",
                            result.input_tokens,
                            result.output_tokens,
                            int((monotonic() - started) * 1000),
                        )
                    )
                    if valid:
                        self.blocked_until.pop(provider.name, None)
                        return Routed(value, tuple(attempts))
                    self.blocked_until[provider.name] = monotonic() + 60
                    break
        unavailable = LLMUnavailable("Nenhum provedor retornou resultado validado.")
        unavailable.attempts = tuple(attempts)
        raise unavailable
