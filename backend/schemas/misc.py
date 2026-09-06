from pydantic import BaseModel
from typing import Optional, List, Literal


class PersonCreate(BaseModel):
    employeeId: str
    name: str
    photoBase64: Optional[str] = None  # consented demo photo, data URL or base64


class PersonOut(BaseModel):
    employeeId: str
    name: str
    photoUrl: Optional[str] = None
    status: str = "AUTHORIZED"
    createdAt: Optional[str] = None


class FencePointIn(BaseModel):
    x: float
    y: float


class FenceCreate(BaseModel):
    cameraId: str
    zoneName: str = "RESTRICTED ZONE"
    points: List[FencePointIn]


class AlertStatusUpdate(BaseModel):
    status: Literal["ACKNOWLEDGED", "RESOLVED"]


class SettingsUpdate(BaseModel):
    weightUnknownPerson: Optional[int] = None
    weightNightMovement: Optional[int] = None
    weightFenceCrossing: Optional[int] = None
    weightVehicleNearby: Optional[int] = None
    weightHighRiskZone: Optional[int] = None
    nightStart: Optional[str] = None
    nightEnd: Optional[str] = None
    visibilityClearThreshold: Optional[int] = None
    visibilityModerateThreshold: Optional[int] = None
    alertCooldownSeconds: Optional[int] = None
    apiUrl: Optional[str] = None
    websocketUrl: Optional[str] = None
    uploadDir: Optional[str] = None
    detectionConfidenceThreshold: Optional[float] = None
