"""
MSWDO Eligibility Prediction System
core/ml_predictor.py

Functions:
  predict_input(ml_input)       → 1 (Eligible) | 0 (Not Eligible)
  compute_score(ml_input)       → int 0–100
  generate_reason(ml_input, prediction) → str
  run_eligibility(client, aid_type)     → EligibilityResult
"""

from dataclasses import dataclass, field

# ── INCOME THRESHOLDS (monthly, in PHP) ──────────────────────
POVERTY_LINE      = 13_000   # indigent / below poverty
NEAR_POOR         = 20_000   # near-poor / vulnerable
PROGRAM_LIMITS = {
    "AICS":        22_000,
    "SEA":         25_000,
    "REDCARD":     25_000,
    "EDUCATIONAL": 30_000,
}
DEFAULT_LIMIT     = 22_000
PASS_SCORE        = 40       # minimum score to be Eligible


@dataclass
class EligibilityResult:
    is_eligible: bool
    score:       int
    label:       str
    reason:      str
    strengths:   list = field(default_factory=list)
    suggestions: list = field(default_factory=list)


# ─────────────────────────────────────────────────────────────
# SCORE ENGINE
# ─────────────────────────────────────────────────────────────
def compute_score(ml_input: dict) -> int:
    """
    Returns a 0–100 eligibility score.
    ml_input keys:
        monthly_income, household_size,
        has_disability, is_senior, previous_aid,
        is_solo_parent, is_indigenous, is_4ps,
        income_per_person (optional — computed if missing)
    """
    score = 0
    income = float(ml_input.get("monthly_income", 0))
    hh     = int(ml_input.get("household_size", 1)) or 1
    income_per_person = ml_input.get("income_per_person") or income / hh

    # ── 1. INCOME (max 30 pts) ────────────────────────────────
    if income <= 0:
        score += 30
    elif income <= POVERTY_LINE:
        score += 28
    elif income <= NEAR_POOR:
        score += 18
    elif income <= 25_000:
        score += 10
    elif income <= 30_000:
        score += 4

    # ── 2. INCOME PER PERSON (max 10 pts) ────────────────────
    if income_per_person <= 2_000:
        score += 10
    elif income_per_person <= 4_000:
        score += 6
    elif income_per_person <= 6_000:
        score += 2

    # ── 3. HOUSEHOLD SIZE (max 15 pts) ───────────────────────
    if hh >= 7:
        score += 15
    elif hh >= 5:
        score += 12
    elif hh >= 4:
        score += 8
    elif hh == 3:
        score += 5
    else:
        score += 2

    # ── 4. VULNERABILITY FLAGS (max 5 pts each) ───────────────
    if ml_input.get("has_disability"):
        score += 5
    if ml_input.get("is_senior"):
        score += 5
    if ml_input.get("is_solo_parent"):
        score += 5
    if ml_input.get("is_indigenous"):
        score += 5
    if ml_input.get("is_4ps"):
        score += 5

    # ── 5. PREVIOUS AID (slight deduction) ───────────────────
    if ml_input.get("previous_aid"):
        score -= 3
    else:
        score += 3

    return max(0, min(100, score))


# ─────────────────────────────────────────────────────────────
# REASON GENERATOR
# ─────────────────────────────────────────────────────────────
def generate_reason(ml_input: dict, prediction: int, aid_type: str = "") -> str:
    """
    Returns a human-readable reason string.
    Called for BOTH eligible and not-eligible outcomes.
    """
    income  = float(ml_input.get("monthly_income", 0))
    hh      = int(ml_input.get("household_size", 1)) or 1
    score   = compute_score(ml_input)
    limit   = PROGRAM_LIMITS.get(aid_type.upper(), DEFAULT_LIMIT)

    positives = []
    negatives = []
    suggestions = []

    # ── Positive factors ─────────────────────────────────────
    if income <= POVERTY_LINE:
        positives.append("income below the poverty threshold")
    elif income <= NEAR_POOR:
        positives.append("income within the near-poor range")
    if hh >= 5:
        positives.append(f"large household ({hh} members)")
    if ml_input.get("has_disability"):
        positives.append("Person with Disability (PWD)")
    if ml_input.get("is_senior"):
        positives.append("Senior Citizen")
    if ml_input.get("is_solo_parent"):
        positives.append("Solo Parent")
    if ml_input.get("is_indigenous"):
        positives.append("Indigenous People (IP)")
    if ml_input.get("is_4ps"):
        positives.append("registered 4Ps beneficiary")
    if not ml_input.get("previous_aid"):
        positives.append("first-time DSWD assistance applicant")

    # ── Negative factors ─────────────────────────────────────
    if income > limit:
        negatives.append(
            f"monthly income of ₱{income:,.2f} exceeds the maximum allowable income "
            f"for {aid_type or 'this'} assistance (₱{limit:,.2f}/month)"
        )
    if income > NEAR_POOR and income <= limit:
        negatives.append(
            f"monthly income of ₱{income:,.2f} reduces the eligibility score"
        )
    if ml_input.get("previous_aid"):
        negatives.append(
            "previous DSWD assistance received — priority is given to first-time beneficiaries"
        )
    if score < PASS_SCORE:
        negatives.append(
            f"overall eligibility score ({score}/100) is below the minimum required score of {PASS_SCORE}"
        )

    # ── Suggestions for ineligible ────────────────────────────
    if prediction == 0:
        aid = aid_type.upper()
        if income <= PROGRAM_LIMITS.get("EDUCATIONAL", 30_000) and aid != "EDUCATIONAL":
            suggestions.append("Educational Assistance (higher income threshold)")
        if income <= PROGRAM_LIMITS.get("SEA", 25_000) and aid != "SEA":
            suggestions.append("SEA – Self-Employment Assistance (livelihood support)")
        if (ml_input.get("has_disability") or ml_input.get("is_senior")
                or ml_input.get("is_solo_parent")) and aid != "AICS":
            suggestions.append("AICS – Crisis Assistance (priority for PWDs, seniors, solo parents)")
        if not suggestions:
            suggestions.append(
                "referral to other government agencies (DOLE, TESDA, DSWD-NHTS, or LGU programs)"
            )

    # ── Build final string ────────────────────────────────────
    parts = []

    if positives:
        parts.append(
            "Qualifying factors: " + "; ".join(positives) + "."
        )

    if prediction == 1:
        parts.insert(0,
            f"The applicant scored {score}/100 and QUALIFIES for assistance."
        )
    else:
        parts.insert(0,
            f"The applicant scored {score}/100 and does NOT qualify for assistance at this time."
        )
        if negatives:
            parts.append("Reasons: " + "; ".join(negatives) + ".")
        if suggestions:
            parts.append(
                "The applicant may be considered for: " + "; ".join(suggestions) + "."
            )
        parts.append(
            "Note: The final determination remains subject to MSWDO staff assessment and validation."
        )

    return " ".join(parts)


# ─────────────────────────────────────────────────────────────
# PREDICT FUNCTION (binary)
# ─────────────────────────────────────────────────────────────
def predict_input(ml_input: dict, aid_type: str = "") -> int:
    """
    Returns 1 (Eligible) or 0 (Not Eligible).
    Hard disqualifiers checked first, then score threshold.
    """
    income = float(ml_input.get("monthly_income", 0))
    aid    = aid_type.upper()
    limit  = PROGRAM_LIMITS.get(aid, DEFAULT_LIMIT)

    # Hard ceiling — income too high
    if income > limit:
        return 0

    score = compute_score(ml_input)
    return 1 if score >= PASS_SCORE else 0


# ─────────────────────────────────────────────────────────────
# CONVENIENCE WRAPPER — pass Client instance directly
# ─────────────────────────────────────────────────────────────
def run_eligibility(client, aid_type: str) -> EligibilityResult:
    """
    Usage in views:
        from core.ml_predictor import run_eligibility
        result = run_eligibility(client, aid_type)
        application.eligibility_result = result.label
        application.eligibility_score  = result.score
        application.eligibility_reason = result.reason
    """
    income = float(client.monthly_income or 0)
    hh     = int(client.household_size or 1) or 1

    ml_input = {
        "monthly_income":   income,
        "household_size":   hh,
        "income_per_person": income / hh,
        "has_disability":   1 if client.has_disability == "Yes" else 0,
        "is_senior":        1 if client.is_senior == "Yes" else 0,
        "previous_aid":     1 if client.previous_aid == "Yes" else 0,
        "is_solo_parent":   1 if getattr(client, "is_solo_parent", "No") == "Yes" else 0,
        "is_indigenous":    1 if getattr(client, "is_indigenous", "No") == "Yes" else 0,
        "is_4ps":           1 if client.is_4ps == "Yes" else 0,
    }

    prediction = predict_input(ml_input, aid_type)
    score      = compute_score(ml_input)
    reason     = generate_reason(ml_input, prediction, aid_type)

    return EligibilityResult(
        is_eligible=bool(prediction),
        score=score,
        label="Eligible" if prediction == 1 else "Not Eligible",
        reason=reason,
    )