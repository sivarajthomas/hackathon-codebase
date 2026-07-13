"""Deterministic leakage calculator.

Computes the policy-correct (expected) charges for a shipment/invoice from the
rate cards and finance policy, then compares them to what was billed. The exact
numbers come from here (never from the LLM); the LLM only reasons over this
breakdown to phrase the root cause / recommendation.

Rules (verified against sample_data/analyzed_data.csv):
  Freight     = BillableWeightKg * BaseRatePerKg(mode)
  Fuel        = Freight * FuelSurchargePercent(mode) / 100
  Surcharges  = per-kg on BillableWeightKg for each applicable flag:
                  Remote 5, Express 8, Overweight(>1000kg) 2, Hazmat 10
  Insurance   = 1.5% of ShipmentValueINR
  ExpectedTotal = Freight + Fuel + Surcharges + Insurance - Discount + Tax
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Built-in defaults matching the sample rate cards. Overridden by any rows the
# user maintains in transport_rates / surcharge_rates.
_DEFAULT_TRANSPORT = {
    "Roadways": (18.0, 8.0),
    "Shipways": (12.0, 5.0),
    "Airways": (42.0, 12.0),
}
_DEFAULT_SURCHARGE_PER_KG = {
    "remote": 5.0,
    "express": 8.0,
    "overweight": 2.0,
    "hazmat": 10.0,
}
_INSURANCE_RATE = 0.015  # 1.5% of shipment value
_OVERWEIGHT_THRESHOLD_KG = 1000.0


@dataclass
class RateCard:
    transport: dict[str, tuple[float, float]] = field(default_factory=lambda: dict(_DEFAULT_TRANSPORT))
    surcharge_per_kg: dict[str, float] = field(default_factory=lambda: dict(_DEFAULT_SURCHARGE_PER_KG))
    insurance_rate: float = _INSURANCE_RATE

    @classmethod
    def from_rows(cls, transport_rows: list[dict], surcharge_rows: list[dict]) -> "RateCard":
        card = cls()
        for r in transport_rows or []:
            mode = str(r.get("TransportMode") or "").strip()
            if mode:
                card.transport[mode] = (
                    _f(r.get("BaseRatePerKg")),
                    _f(r.get("FuelSurchargePercent")),
                )
        for r in surcharge_rows or []:
            stype = str(r.get("SurchargeType") or "").lower()
            rate = _f(r.get("Rate"))
            if "remote" in stype:
                card.surcharge_per_kg["remote"] = rate
            elif "express" in stype:
                card.surcharge_per_kg["express"] = rate
            elif "overweight" in stype:
                card.surcharge_per_kg["overweight"] = rate
            elif "hazard" in stype:
                card.surcharge_per_kg["hazmat"] = rate
            elif "insurance" in stype:
                card.insurance_rate = rate / 100.0
        return card


@dataclass
class LeakageResult:
    expected_freight: float
    billed_freight: float
    expected_fuel: float
    billed_fuel: float
    expected_surcharges: float
    billed_surcharges: float
    expected_insurance: float
    billed_insurance: float
    expected_total: float
    billed_total: float
    leakage_amount: float
    leakage_type: str
    severity: str
    anomaly: bool
    gaps: dict[str, float]
    surcharge_breakdown: dict[str, float]
    notes: list[str]

    def is_leaking(self) -> bool:
        return self.anomaly and round(self.leakage_amount, 2) != 0.0


def compute(invoice: dict[str, Any], shipment: dict[str, Any], card: RateCard) -> LeakageResult:
    mode = str(shipment.get("ModeOfTransport") or "").strip()
    billable = _f(shipment.get("BillableWeightKg"))
    measured = _f(shipment.get("MeasuredWeightKg"))
    value = _f(shipment.get("ShipmentValueINR"))

    base_rate, fuel_pct = card.transport.get(mode, (0.0, 0.0))
    expected_freight = round(billable * base_rate, 2)
    expected_fuel = round(expected_freight * fuel_pct / 100.0, 2)

    breakdown: dict[str, float] = {}
    if _flag(shipment.get("RemoteAreaFlag")):
        breakdown["Remote Area Delivery"] = round(billable * card.surcharge_per_kg["remote"], 2)
    if _flag(shipment.get("ExpressFlag")):
        breakdown["Express Delivery"] = round(billable * card.surcharge_per_kg["express"], 2)
    if billable > _OVERWEIGHT_THRESHOLD_KG:
        breakdown["Overweight Handling"] = round(billable * card.surcharge_per_kg["overweight"], 2)
    if _flag(shipment.get("HazardousFlag")):
        breakdown["Hazardous Material Handling"] = round(billable * card.surcharge_per_kg["hazmat"], 2)
    expected_surcharges = round(sum(breakdown.values()), 2)

    expected_insurance = round(value * card.insurance_rate, 2)

    discount = _f(invoice.get("DiscountAmount"))
    tax = _f(invoice.get("TaxAmount"))

    billed_freight = _f(invoice.get("FreightCharge"))
    billed_fuel = _f(invoice.get("FuelSurcharge"))
    billed_surcharges = _f(invoice.get("OtherSurcharge"))
    billed_insurance = _f(invoice.get("InsuranceCharge"))
    billed_total = _f(invoice.get("TotalInvoiceAmount"))

    expected_total = round(
        expected_freight + expected_fuel + expected_surcharges + expected_insurance - discount + tax,
        2,
    )
    leakage_amount = round(expected_total - billed_total, 2)

    gaps = {
        "freight": round(expected_freight - billed_freight, 2),
        "fuel": round(expected_fuel - billed_fuel, 2),
        "surcharges": round(expected_surcharges - billed_surcharges, 2),
        "insurance": round(expected_insurance - billed_insurance, 2),
    }

    notes: list[str] = []
    # Weight-integrity signal: billed on more weight than was measured/shipped.
    if measured and billable - measured > 1.0:
        notes.append(
            f"Billable weight ({billable:g}kg) exceeds measured weight ({measured:g}kg)."
        )

    leakage_type = _classify(gaps, notes)
    anomaly = abs(leakage_amount) >= 1.0 or any(abs(g) >= 1.0 for g in gaps.values())
    severity = _severity(abs(leakage_amount), expected_total)

    return LeakageResult(
        expected_freight=expected_freight,
        billed_freight=billed_freight,
        expected_fuel=expected_fuel,
        billed_fuel=billed_fuel,
        expected_surcharges=expected_surcharges,
        billed_surcharges=billed_surcharges,
        expected_insurance=expected_insurance,
        billed_insurance=billed_insurance,
        expected_total=expected_total,
        billed_total=billed_total,
        leakage_amount=leakage_amount,
        leakage_type=leakage_type,
        severity=severity,
        anomaly=anomaly,
        gaps=gaps,
        surcharge_breakdown=breakdown,
        notes=notes,
    )


def _classify(gaps: dict[str, float], notes: list[str]) -> str:
    """Pick a human leakage label from the dominant component gap."""
    labels_under = {
        "insurance": "Insurance Underbilled",
        "surcharges": "Surcharge Not Billed",
        "freight": "Freight Underbilled",
        "fuel": "Fuel Surcharge Underbilled",
    }
    labels_over = {
        "insurance": "Insurance Overbilled",
        "surcharges": "Surcharge Overbilled",
        "freight": "Freight Overbilled",
        "fuel": "Duplicate/Excess Fuel Surcharge",
    }
    # Largest absolute gap wins.
    key = max(gaps, key=lambda k: abs(gaps[k]))
    if abs(gaps[key]) < 1.0:
        return "Weight Billed Higher Than Shipped" if notes else "No Anomaly"
    return (labels_under if gaps[key] > 0 else labels_over)[key]


def _severity(leak: float, expected_total: float) -> str:
    ratio = (leak / expected_total) if expected_total else 0.0
    if leak >= 50000 or ratio >= 0.20:
        return "high"
    if leak >= 10000 or ratio >= 0.08:
        return "medium"
    return "low"


def _f(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _flag(value: Any) -> bool:
    return str(value).strip() in {"1", "true", "True", "yes", "Y"}
