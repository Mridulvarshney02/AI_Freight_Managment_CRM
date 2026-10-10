from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class DiscoveryRequest(BaseModel):
    query_id: int = Field(gt=0)
    pod: str = Field(min_length=1, pattern=r"\S")
    booking_region: str = Field(min_length=1, pattern=r"\S")
    cargo_ready_date: date | None = None


class EvidenceSource(BaseModel):
    # Assigned by our retrieval code, not invented by the LLM.
    source_id: str
    source_type: Literal[
        "workbook",
        "port_directory",
        "official_port",
        "official_carrier",
        "official_agent",
        "other",
    ]
    reference: str
    retrieved_at: datetime
    excerpt: str
    title: str | None = None
    search_query: str | None = None
    search_score: float | None = None
    search_request_id: str | None = None
    relevance_status: Literal[
        "not_checked",
        "potentially_relevant",
        "needs_review",
    ] = "not_checked"


class PortFinding(BaseModel):
    input_name: str
    status: Literal[
        "identified",
        "ambiguous",
        "unresolved",
    ]
    official_name: str | None = None
    country: str | None = None
    location_code: str | None = None
    alternatives: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    explanation: str

    @model_validator(mode="after")
    def require_identity_evidence(self):
        if self.status == "identified":
            if not self.official_name or not self.country:
                raise ValueError(
                    "An identified port requires a name and country."
                )
            if not self.evidence_ids:
                raise ValueError(
                    "An identified port requires supporting evidence."
                )
        return self


class LaneFinding(BaseModel):
    status: Literal[
        "existing_lane_matched",
        "new_lane_proposed",
        "unresolved",
    ]
    lane_name: str | None = None
    explanation: str
    evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_lane_name(self):
        if self.status != "unresolved" and not self.lane_name:
            raise ValueError("A lane classification requires a name.")
        return self


class CarrierFinding(BaseModel):
    shipping_line: str
    pol: str
    pod: str

    status: Literal[
        "candidate",
        "published_route_found",
        "confirmation_required",
        "explicitly_unavailable",
    ]

    routing_type: Literal[
        "direct",
        "transshipment",
        "unknown",
    ] = "unknown"

    transshipment_ports: list[str] = Field(default_factory=list)

    quotation_channel: Literal[
        "portal",
        "office",
        "unknown",
    ] = "unknown"

    evidence_ids: list[str] = Field(default_factory=list)
    explanation: str
    outstanding_checks: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_route_evidence(self):
        if self.status in {
            "published_route_found",
            "explicitly_unavailable",
        } and not self.evidence_ids:
            raise ValueError(
                "Route availability claims require evidence."
            )

        if self.routing_type == "direct" and self.transshipment_ports:
            raise ValueError(
                "A direct routing cannot contain transshipment ports."
            )

        return self


class DiscoveryResult(BaseModel):
    query_id: int
    pol: str
    pod: str
    booking_region: str
    container_type: str
    cargo_ready_date: date | None = None

    status: Literal[
        "findings_available",
        "needs_clarification",
        "unresolved",
    ]

    port: PortFinding
    trade_lane: LaneFinding
    carriers: list[CarrierFinding] = Field(default_factory=list)
    sources: list[EvidenceSource] = Field(default_factory=list)
    outstanding_questions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_evidence_references(self):
        source_ids = [source.source_id for source in self.sources]

        if len(source_ids) != len(set(source_ids)):
            raise ValueError("Evidence source IDs must be unique.")

        known_ids = set(source_ids)
        findings = [self.port, self.trade_lane, *self.carriers]

        for finding in findings:
            unknown_ids = set(finding.evidence_ids) - known_ids
            if unknown_ids:
                raise ValueError(
                    f"Unknown evidence references: {sorted(unknown_ids)}"
                )

        return self