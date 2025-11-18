from enum import Enum
from datetime import datetime

from pydantic import Field, BaseModel


class EventType(Enum):
    SUBMITTAL_APPROVED = "Submittal_Approved"
    SHIPMENT_DEPARTED_FACTORY = "Shipment_Departed_Factory"
    SHIPMENT_ARRIVED_SITE = "Shipment_Arrived_Site"
    INSPECTION_FAILED = "Inspection_Failed"
    INSPECTION_PASSED = "Inspection_Passed"
    HUMAN_INPUT = "Human_Input"

class SubmitalApprovalEvent(BaseModel):
    event_type: EventType = Field(default=EventType.SUBMITTAL_APPROVED)
    item: str
    document_url: str
    document_name: str

class ShipmentDepartedFactoryEvent(BaseModel):
    event_type: EventType = Field(default=EventType.SHIPMENT_DEPARTED_FACTORY)
    item: str
    eta: datetime
    date_departed: datetime
    location_address: str

class ShipmentArrivedSiteEvent(BaseModel):
    event_type: EventType = Field(default=EventType.SHIPMENT_ARRIVED_SITE)
    item: str
    date_arrived: datetime
    location_address: str

class InspectionFailedEvent(BaseModel):
    event_type: EventType = Field(default=EventType.INSPECTION_FAILED)
    item: str
    inspection_date: datetime
    document_url: str
    document_name: str

class InspectionPassedEvent(BaseModel):
    event_type: EventType = Field(default=EventType.INSPECTION_PASSED)
    item: str
    inspection_date: datetime
    document_url: str
    document_name: str