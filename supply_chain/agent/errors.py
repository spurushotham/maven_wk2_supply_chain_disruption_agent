"""Classify provider errors without exposing raw messages or credentials."""
QUOTA_CODES = {"insufficient_quota", "billing_hard_limit_reached", "billing_not_active",
               "organization_spend_limit_exceeded", "organization_usage_limit_exceeded",
               "project_spend_limit_exceeded", "insufficient_credits"}
RATE_CODES = {"rate_limit_exceeded", "rate_limit_error", "slow_down"}


def classify_api_error(exc):
    codes = set()
    seen = set()
    current = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        for value in (getattr(current, "code", None), getattr(current, "type", None)):
            if isinstance(value, str) and value in QUOTA_CODES | RATE_CODES:
                codes.add(value)
        body = getattr(current, "body", None)
        response = getattr(current, "response", None)
        bodies = [body]
        if response is not None:
            try:
                bodies.append(response.json())
            except Exception:
                pass
        for body in bodies:
            if isinstance(body, dict):
                for record in (body, body.get("error", {})):
                    if isinstance(record, dict):
                        for key in ("code", "type"):
                            value = record.get(key)
                            if isinstance(value, str) and value in QUOTA_CODES | RATE_CODES:
                                codes.add(value)
        current = current.__cause__ or current.__context__
    kind = "quota" if codes & QUOTA_CODES else "rate" if codes & RATE_CODES else "unknown"
    return {"kind": kind, "codes": sorted(codes)}
