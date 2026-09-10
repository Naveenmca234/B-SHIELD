"""
multi_cue_engine.py
--------------------
Combines all contextual evidence into a single, transparent, explainable
risk score (0-100) and severity level. This is the core policy enforced
throughout IBVAP: no single weak signal (night, rain, one vehicle) is
ever enough on its own to declare a confirmed intrusion - severity comes
from the WEIGHTED COMBINATION of cues, and every score is accompanied by
a human-readable breakdown of exactly which cues contributed and by how
much (spec section 41: "This makes the AI decision transparent and
explainable.").
"""
from typing import Optional
from dataclasses import dataclass


@dataclass
class ThreatWeights:
    unknown_person: int = 30
    night_movement: int = 15
    fence_crossing: int = 30
    vehicle_nearby: int = 10
    high_risk_zone: int = 15
    predictive_trajectory: int = 15
    loitering: int = 20
    confidence_weight: int = 10
    audio_anomaly: int = 15


@dataclass
class ThreatInputs:
    person_detected: bool = False
    person_status: Optional[str] = None          # 'AUTHORIZED' | 'UNKNOWN' | None
    detection_confidence: Optional[float] = None # 0.0 - 1.0 optical detector confidence
    is_night: bool = False
    fence_crossing: bool = False
    restricted_zone_activity: bool = False
    predicted_zone_entry: bool = False
    is_loitering: bool = False
    motion_detected: bool = False
    vehicle_nearby: bool = False
    bicycle_nearby: bool = False
    visibility_status: str = "CLEAR"              # CLEAR | MODERATE | POOR
    camera_risk_level: str = "MEDIUM"             # LOW | MEDIUM | HIGH
    movement_pattern: Optional[str] = None        # e.g. 'loitering', 'approaching_fence'
    audio_anomaly: Optional[str] = None           # 'LOUD_IMPULSE_DETECTED' | 'SUSTAINED_LOUD_AUDIO' | None



def severity_from_score(score: int) -> str:
    if score <= 30:
        return "LOW"
    elif score <= 60:
        return "MEDIUM"
    elif score <= 80:
        return "HIGH"
    else:
        return "CRITICAL"


def compute_threat(inputs: ThreatInputs, weights: ThreatWeights = ThreatWeights()) -> dict:
    """
    Returns: {riskScore, severity, eventType, explanation, breakdown: [...]}
    Formula combines:
    LOCATION RISK (fence, restricted zone, camera risk level)
    + MOVEMENT RISK (trajectory prediction, loitering, motion)
    + TIME RISK (night illumination)
    + CONFIDENCE ADJUSTMENT (optical detection confidence)
    """
    score = 0
    breakdown = []  # list of {label, points}
    explanation_parts = []

    is_unknown = inputs.person_detected and inputs.person_status == "UNKNOWN"

    if is_unknown:
        score += weights.unknown_person
        breakdown.append({"label": "Unknown Person", "points": weights.unknown_person})
        explanation_parts.append("An unknown person was detected")
    elif inputs.person_detected and inputs.person_status == "AUTHORIZED":
        explanation_parts.append("An authorized person was detected")

    # Optical detection confidence contribution
    if inputs.person_detected and inputs.detection_confidence is not None:
        if inputs.detection_confidence >= 0.8:
            score += weights.confidence_weight
            breakdown.append({"label": "High Detection Confidence", "points": weights.confidence_weight})
            explanation_parts.append(f"with high optical detection confidence ({int(inputs.detection_confidence * 100)}%)")
        elif inputs.detection_confidence < 0.4:
            deduction = max(5, int(weights.confidence_weight * 0.5))
            score -= deduction
            breakdown.append({"label": "Low Detection Confidence", "points": -deduction})
            explanation_parts.append(f"with marginal detection confidence ({int(inputs.detection_confidence * 100)}%)")

    # Time risk: Night movement
    if inputs.is_night and (inputs.person_detected or inputs.vehicle_nearby or inputs.motion_detected):
        score += weights.night_movement
        breakdown.append({"label": "Night Movement", "points": weights.night_movement})
        explanation_parts.append("during night-time hours")

    # Location risk: Virtual fence crossing & zone activity
    if inputs.fence_crossing:
        score += weights.fence_crossing
        breakdown.append({"label": "Fence Crossing", "points": weights.fence_crossing})
        explanation_parts.append("and crossed the configured virtual fence")
    elif inputs.restricted_zone_activity:
        score += int(weights.fence_crossing * 0.5)
        breakdown.append({"label": "Restricted Zone Activity", "points": int(weights.fence_crossing * 0.5)})
        explanation_parts.append("near a restricted zone")

    # Movement risk: Loitering / Dwell time
    if inputs.is_loitering or inputs.movement_pattern == "loitering":
        score += weights.loitering
        breakdown.append({"label": "Loitering Detection", "points": weights.loitering})
        explanation_parts.append("prolonged loitering detected inside restricted perimeter")

    # Movement risk: Predictive trajectory toward restricted zone
    if inputs.predicted_zone_entry and not inputs.fence_crossing:
        score += weights.predictive_trajectory
        breakdown.append({"label": "Predictive Trajectory", "points": weights.predictive_trajectory})
        explanation_parts.append("Short-term trajectory projects movement toward the restricted zone")

    if inputs.vehicle_nearby:
        score += weights.vehicle_nearby
        breakdown.append({"label": "Vehicle Nearby", "points": weights.vehicle_nearby})
        explanation_parts.append("A vehicle was detected nearby, increasing the calculated risk level")

    if inputs.bicycle_nearby:
        score += max(1, weights.vehicle_nearby // 2)
        breakdown.append({"label": "Bicycle Nearby", "points": max(1, weights.vehicle_nearby // 2)})

    if inputs.camera_risk_level == "HIGH":
        score += weights.high_risk_zone
        breakdown.append({"label": "High-Risk Zone", "points": weights.high_risk_zone})
        explanation_parts.append("This camera covers a designated high-risk zone")

    if inputs.audio_anomaly == "LOUD_IMPULSE_DETECTED":
        score += weights.audio_anomaly
        breakdown.append({"label": "Loud Audio Impulse", "points": weights.audio_anomaly})
        explanation_parts.append("A sudden loud acoustic impulse was detected in the perimeter sector")
    elif inputs.audio_anomaly == "SUSTAINED_LOUD_AUDIO":
        pts = max(5, int(weights.audio_anomaly * 0.7))
        score += pts
        breakdown.append({"label": "Sustained Loud Audio", "points": pts})
        explanation_parts.append("Sustained elevated acoustic noise was detected")


    # --- Poor visibility handling (never itself a critical cause) ---
    event_type = "NORMAL"
    if inputs.visibility_status == "POOR":
        supporting_cues = sum([
            inputs.motion_detected,
            inputs.fence_crossing or inputs.restricted_zone_activity,
            inputs.vehicle_nearby or inputs.bicycle_nearby,
        ])
        if supporting_cues >= 2 and not inputs.person_detected:
            event_type = "POSSIBLE_INTRUSION"
            score = max(score, 45)  # push into MEDIUM/HIGH range, never auto-CRITICAL
            explanation_parts.append(
                "Visibility is poor and direct person detection is unreliable, but multiple "
                "supporting cues (motion, zone activity, vehicle presence) suggest possible intrusion"
            )
        else:
            explanation_parts.append(
                "Visibility is currently poor; detection confidence may be reduced"
            )

    score = max(0, min(100, score))
    severity = severity_from_score(score)

    # --- Determine primary event type if not already set by visibility logic ---
    if event_type == "NORMAL":
        if inputs.fence_crossing:
            event_type = "INTRUSION_DETECTED"
        elif inputs.is_loitering or inputs.movement_pattern == "loitering":
            event_type = "LOITERING_DETECTED"
        elif is_unknown and inputs.is_night:
            event_type = "NIGHT_MOVEMENT"
        elif is_unknown:
            event_type = "UNKNOWN_PERSON"
        elif inputs.vehicle_nearby:
            event_type = "VEHICLE_DETECTED"
        elif severity in ("HIGH", "CRITICAL"):
            event_type = "HIGH_THREAT" if severity == "HIGH" else "CRITICAL_THREAT"

    if not explanation_parts:
        explanation = "No significant risk factors detected."
    else:
        explanation = " ".join(explanation_parts).strip() + "."
        explanation = explanation[0].upper() + explanation[1:]

    return {
        "riskScore": score,
        "severity": severity,
        "eventType": event_type,
        "explanation": explanation,
        "breakdown": breakdown,
    }
