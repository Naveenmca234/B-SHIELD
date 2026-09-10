from pydantic import BaseModel
from typing import Literal, Optional, List

SourceType = Literal["WEBCAM", "VIDEO_FILE", "RTSP"]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]


class FencePoint(BaseModel):
    x: float
    y: float


class CameraCreate(BaseModel):
    cameraId: str
    name: str
    location: str
    sourceType: SourceType
    rtspUrl: Optional[str] = None
    videoFile: Optional[str] = None
    riskLevel: RiskLevel = "MEDIUM"
    nightStart: str = "18:30"
    nightEnd: str = "06:00"
    enabled: bool = True
    fence: Optional[List[FencePoint]] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    mapZone: Optional[str] = None
    mapX: Optional[float] = None
    mapY: Optional[float] = None


class CameraUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    sourceType: Optional[SourceType] = None
    rtspUrl: Optional[str] = None
    videoFile: Optional[str] = None
    riskLevel: Optional[RiskLevel] = None
    nightStart: Optional[str] = None
    nightEnd: Optional[str] = None
    enabled: Optional[bool] = None
    fence: Optional[List[FencePoint]] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    mapZone: Optional[str] = None
    mapX: Optional[float] = None
    mapY: Optional[float] = None



class CameraOut(CameraCreate):
    status: str = "OFFLINE"
    createdAt: Optional[str] = None
