"""
Structured UDS (ISO 14229) knowledge model. Plain dataclasses (not new DB
tables — persisted via the existing DiagnosticKnowledgeUnit table, see
repository.py) so later stages (request construction, validation, test
generation) can consume a typed, serializable representation.

Every entity carries a SourceReference. Fields with no approved-source value
stay None/unknown — never guessed or invented.
"""
from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class SourceReference:
    document_id: Optional[str] = None
    document_name: Optional[str] = None
    document_version: Optional[int] = None
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    chunk_id: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Optional["SourceReference"]:
        if not data:
            return None
        return cls(**{k: data.get(k) for k in cls.__dataclass_fields__})


@dataclass
class UdsNrc:
    nrc: str  # e.g. "0x13"
    nrc_name: Optional[str] = None
    description: Optional[str] = None
    applicable_service: Optional[str] = None
    applicable_conditions: Optional[str] = None
    source: Optional[SourceReference] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["source"] = self.source.to_dict() if self.source else None
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "UdsNrc":
        data = dict(data)
        data["source"] = SourceReference.from_dict(data.get("source"))
        return cls(**data)


@dataclass
class UdsDid:
    did: str  # e.g. "0xF190"
    name: Optional[str] = None
    description: Optional[str] = None
    data_length: Optional[int] = None
    access: Optional[str] = None  # e.g. "read", "read/write"
    request_info: Optional[str] = None
    response_info: Optional[str] = None
    source: Optional[SourceReference] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["source"] = self.source.to_dict() if self.source else None
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "UdsDid":
        data = dict(data)
        data["source"] = SourceReference.from_dict(data.get("source"))
        return cls(**data)


@dataclass
class UdsRid:
    rid: str  # e.g. "0x0203"
    name: Optional[str] = None
    description: Optional[str] = None
    request_info: Optional[str] = None
    response_info: Optional[str] = None
    source: Optional[SourceReference] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["source"] = self.source.to_dict() if self.source else None
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "UdsRid":
        data = dict(data)
        data["source"] = SourceReference.from_dict(data.get("source"))
        return cls(**data)


@dataclass
class UdsSubfunction:
    service_id: str
    subfunction_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    request_info: Optional[str] = None
    response_info: Optional[str] = None
    source: Optional[SourceReference] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["source"] = self.source.to_dict() if self.source else None
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "UdsSubfunction":
        data = dict(data)
        data["source"] = SourceReference.from_dict(data.get("source"))
        return cls(**data)


@dataclass
class UdsService:
    service_id: str  # e.g. "0x22"
    service_name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    subfunctions: list[UdsSubfunction] = field(default_factory=list)
    request_structure: Optional[str] = None
    positive_response_structure: Optional[str] = None
    negative_response_structure: Optional[str] = None
    nrcs: list[UdsNrc] = field(default_factory=list)
    source: Optional[SourceReference] = None

    def to_dict(self) -> dict:
        return {
            "service_id": self.service_id,
            "service_name": self.service_name,
            "description": self.description,
            "category": self.category,
            "subfunctions": [s.to_dict() for s in self.subfunctions],
            "request_structure": self.request_structure,
            "positive_response_structure": self.positive_response_structure,
            "negative_response_structure": self.negative_response_structure,
            "nrcs": [n.to_dict() for n in self.nrcs],
            "source": self.source.to_dict() if self.source else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UdsService":
        return cls(
            service_id=data["service_id"],
            service_name=data.get("service_name"),
            description=data.get("description"),
            category=data.get("category"),
            subfunctions=[UdsSubfunction.from_dict(s) for s in data.get("subfunctions", [])],
            request_structure=data.get("request_structure"),
            positive_response_structure=data.get("positive_response_structure"),
            negative_response_structure=data.get("negative_response_structure"),
            nrcs=[UdsNrc.from_dict(n) for n in data.get("nrcs", [])],
            source=SourceReference.from_dict(data.get("source")),
        )


# --- Request / response representations (used by Stages 9-10) -------------

@dataclass
class UdsRequest:
    service_id: str
    subfunction_id: Optional[str] = None
    did: Optional[str] = None
    rid: Optional[str] = None
    parameters: dict = field(default_factory=dict)
    request_bytes: Optional[str] = None  # hex string, e.g. "22 F1 90"
    source: Optional[SourceReference] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["source"] = self.source.to_dict() if self.source else None
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "UdsRequest":
        data = dict(data)
        data["source"] = SourceReference.from_dict(data.get("source"))
        return cls(**data)


@dataclass
class UdsPositiveResponse:
    service_id: str  # response SID (conventionally request SID + 0x40)
    parameters: dict = field(default_factory=dict)
    response_bytes: Optional[str] = None
    source: Optional[SourceReference] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["source"] = self.source.to_dict() if self.source else None
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "UdsPositiveResponse":
        data = dict(data)
        data["source"] = SourceReference.from_dict(data.get("source"))
        return cls(**data)


@dataclass
class UdsNegativeResponse:
    original_service_id: str
    nrc: str
    negative_response_sid: str = "0x7F"
    description: Optional[str] = None
    source: Optional[SourceReference] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["source"] = self.source.to_dict() if self.source else None
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "UdsNegativeResponse":
        data = dict(data)
        data["source"] = SourceReference.from_dict(data.get("source"))
        return cls(**data)
