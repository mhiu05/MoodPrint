"""Opt-in shared-NAT candidate. One API process; upstream CAPTCHA remains authoritative."""

from app.core.limits import AttemptLimiter


class AuthAdmission:
    def __init__(self):
        limited = ("AUTH_RATE_LIMITED", "Bạn đã thử quá nhiều lần. Vui lòng đợi vài phút.")
        # Signup/confirm/login each allow the 100-person event cohort plus headroom.
        self.actions = {name: AttemptLimiter(150, 60, *limited)
                        for name in ("signup", "confirmation", "recovery", "login", "reset")}
        self.aggregate = AttemptLimiter(600, 900, *limited)

    def check(self, action: str, client_key: str) -> None:
        self.aggregate.check(client_key)
        self.actions[action].check(client_key)
