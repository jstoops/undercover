"""The shapes of the API's requests and responses."""

from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

Status = Literal[
    "waiting", "in_progress", "awaiting_sign_off", "decided", "left_for_handler"
]
DecisionKind = Literal["approve", "decline", "refer"]
StepKind = Literal["tool_call", "tool_result", "reply", "error"]
RunStatus = Literal["running", "finished", "stopped"]
TodoStatus = Literal["pending", "in_progress", "completed"]


class DecisionInput(BaseModel):
    decision: DecisionKind
    payout: float = Field(ge=0)
    reason: str = Field(min_length=1)
    policy_section: str = Field(min_length=1)

    @model_validator(mode="after")
    def payout_fits_decision(self) -> Self:
        if self.decision == "approve" and self.payout <= 0:
            raise ValueError("An approval needs a payout above zero")
        if self.decision != "approve" and self.payout != 0:
            raise ValueError("A decline or a referral has a payout of zero")
        return self


class PaymentInput(BaseModel):
    amount: float = Field(gt=0)


class SignOffInput(BaseModel):
    handler_id: str


class FailureInput(BaseModel):
    thread_id: str
    reason: str = Field(min_length=1)


class StepInput(BaseModel):
    thread_id: str
    kind: StepKind
    name: str
    content: str


class Step(StepInput):
    step_id: int
    claim_id: str
    created_at: str


class Instructions(BaseModel):
    queue: str
    claim: str


class Item(BaseModel):
    description: str
    category: str
    amount: float


class ClaimDocument(BaseModel):
    name: str
    type: str
    content: str


class Decision(BaseModel):
    decision: DecisionKind
    payout: float
    reason: str
    policy_section: str
    decided_at: str


class SignOff(BaseModel):
    handler_id: str
    handler_name: str
    signed_off_at: str


class Payment(BaseModel):
    amount: float
    paid_at: str


class ClaimSummary(BaseModel):
    claim_id: str
    customer_name: str
    claim_type: str
    summary: str
    submitted_on: str
    amount_claimed: float
    status: Status
    failures: int
    decision: DecisionKind | None
    payout: float | None


class Claim(BaseModel):
    claim_id: str
    policy_id: str
    customer_id: str
    customer_name: str
    claim_type: str
    submitted_on: str
    incident_date: str
    incident_location: str
    summary: str
    story: str
    items: list[Item]
    amount_claimed: float
    documents: list[ClaimDocument]
    status: Status
    failures: int
    decision: Decision | None
    sign_off: SignOff | None
    payment: Payment | None


class Trip(BaseModel):
    destination: str
    departs_on: str
    returns_on: str
    trip_cost: float


class Policy(BaseModel):
    policy_id: str
    customer_id: str
    plan: str
    add_ons: list[str]
    purchased_on: str
    sold_through: str
    trip: Trip
    travelers: list[str]
    status: str


class PreviousClaim(BaseModel):
    claim_id: str
    filed_on: str
    incident_date: str
    claim_type: str
    summary: str
    outcome: str
    amount_paid: float


class Customer(BaseModel):
    customer_id: str
    name: str
    customer_since: str
    previous_claims: list[PreviousClaim]


class Handler(BaseModel):
    handler_id: str
    name: str
    role: str
    can_approve_over_limit: bool


class RunInput(BaseModel):
    cap: int = Field(ge=1)


class TodoInput(BaseModel):
    content: str
    status: TodoStatus


class TodosInput(BaseModel):
    todos: list[TodoInput]


class FinishInput(BaseModel):
    outcome: Literal["finished", "stopped"]
    summary: str


class Todo(BaseModel):
    position: int
    content: str
    status: TodoStatus


class Run(BaseModel):
    run_id: int
    cap: int
    status: RunStatus
    started_at: str
    finished_at: str | None
    summary: str | None
    todos: list[Todo]


class SectionSummary(BaseModel):
    number: int
    title: str
    topics: list[str]


class Section(BaseModel):
    document: str
    number: int
    title: str
    text: str
