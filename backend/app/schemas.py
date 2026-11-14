from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
    email: str
    password: str = Field(min_length=8)
    name: str


class LoginIn(BaseModel):
    email: str
    password: str


class AuthOut(BaseModel):
    token: str
    user_id: int
    email: str
    name: str


class BrandCreate(BaseModel):
    name: str
    website: Optional[str] = None
    channels: List[str] = []
    notes: Optional[str] = None


class BrandOut(BaseModel):
    id: int
    name: str
    website: Optional[str] = None
    channels: List[str] = []
    status: str
    approved: bool
    notes: Optional[str] = None


class OnboardingIn(BaseModel):
    audience: Optional[str] = None
    tone: Optional[str] = None
    goals: Optional[str] = None
    assets: Optional[str] = None
    approval_notes: Optional[str] = None


class OnboardingOut(OnboardingIn):
    brand_id: int


class MeOut(BaseModel):
    id: int
    email: str
    name: str
    role: str


class TeamCreateIn(BaseModel):
    name: str
    description: Optional[str] = None


class TeamOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    owner_id: int


class TeamMemberAddIn(BaseModel):
    email: str
    role: str = Field(default='agent')


class TeamMemberOut(BaseModel):
    id: int
    team_id: int
    user_id: int
    name: str
    email: str
    role: str


class DelegationCreateIn(BaseModel):
    title: str
    brief: Optional[str] = None
    assigned_role: str


class DelegationUpdateIn(BaseModel):
    status: Optional[str] = None
    brief: Optional[str] = None
    source: Optional[str] = None


class DelegationOut(BaseModel):
    id: int
    team_id: int
    created_by_id: int
    title: str
    brief: Optional[str] = None
    assigned_role: str
    source: str
    status: str


class TelegramInboundIn(BaseModel):
    team_id: int
    chat_id: Optional[str] = None
    user_handle: Optional[str] = None
    text: str


class TelegramInboundOut(BaseModel):
    accepted: bool
    parsed_action: str
    task_id: Optional[int] = None
    message: str


class CampaignCreateIn(BaseModel):
    name: str
    goal: Optional[str] = None
    platform: Optional[str] = None


class CampaignUpdateIn(BaseModel):
    status: Optional[str] = None
    goal: Optional[str] = None
    platform: Optional[str] = None


class CampaignOut(BaseModel):
    id: int
    team_id: int
    created_by_id: int
    name: str
    goal: Optional[str] = None
    platform: Optional[str] = None
    status: str


class ContentCreateIn(BaseModel):
    channel: str
    title: str
    draft: Optional[str] = None
    status: str = 'draft'
    scheduled_for: Optional[datetime] = None


class ContentUpdateIn(BaseModel):
    channel: Optional[str] = None
    title: Optional[str] = None
    draft: Optional[str] = None
    status: Optional[str] = None
    scheduled_for: Optional[datetime] = None


class ContentOut(BaseModel):
    id: int
    campaign_id: int
    created_by_id: int
    channel: str
    title: str
    draft: Optional[str] = None
    status: str
    scheduled_for: Optional[datetime] = None


class ContentMetricCreateIn(BaseModel):
    impressions: int = 0
    clicks: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    recorded_at: Optional[datetime] = None


class ContentMetricOut(BaseModel):
    id: int
    content_item_id: int
    created_by_id: int
    impressions: int
    clicks: int
    likes: int
    comments: int
    shares: int
    recorded_at: datetime


class ContentMetricSummary(BaseModel):
    content_item_id: int
    title: str
    channel: str
    status: str
    impressions: int
    clicks: int
    likes: int
    comments: int
    shares: int


class CampaignAnalyticsOut(BaseModel):
    campaign_id: int
    content_count: int
    totals: dict[str, int]
    items: list[ContentMetricSummary]


class PublishJobCreateIn(BaseModel):
    scheduled_for: Optional[datetime] = None


class PublishJobUpdateIn(BaseModel):
    status: Optional[str] = None
    attempts: Optional[int] = None
    last_error: Optional[str] = None
    published_at: Optional[datetime] = None
    scheduled_for: Optional[datetime] = None


class PublishJobOut(BaseModel):
    id: int
    team_id: int
    campaign_id: int
    content_item_id: int
    created_by_id: int
    status: str
    scheduled_for: Optional[datetime] = None
    attempts: int
    last_error: Optional[str] = None
    published_at: Optional[datetime] = None
