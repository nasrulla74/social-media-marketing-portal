from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default='customer', nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    sessions = relationship('SessionToken', back_populates='user', cascade='all, delete-orphan')
    brands = relationship('Brand', back_populates='owner', cascade='all, delete-orphan')
    team_memberships = relationship('TeamMember', back_populates='user', cascade='all, delete-orphan')
    created_delegations = relationship('DelegationTask', back_populates='created_by', cascade='all, delete-orphan')
    created_campaigns = relationship('Campaign', back_populates='created_by', cascade='all, delete-orphan')
    created_content_items = relationship('ContentItem', back_populates='created_by', cascade='all, delete-orphan')
    created_metrics = relationship('ContentMetric', back_populates='created_by', cascade='all, delete-orphan')
    created_publish_jobs = relationship('PublishJob', back_populates='created_by', cascade='all, delete-orphan')


class SessionToken(Base):
    __tablename__ = 'sessions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship('User', back_populates='sessions')


class Team(Base):
    __tablename__ = 'teams'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    owner = relationship('User')
    members = relationship('TeamMember', back_populates='team', cascade='all, delete-orphan')
    delegations = relationship('DelegationTask', back_populates='team', cascade='all, delete-orphan')
    campaigns = relationship('Campaign', back_populates='team', cascade='all, delete-orphan')
    publish_jobs = relationship('PublishJob', back_populates='team', cascade='all, delete-orphan')


class TeamMember(Base):
    __tablename__ = 'team_members'
    __table_args__ = (UniqueConstraint('team_id', 'user_id', name='uq_team_user'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey('teams.id'), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default='agent', nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    team = relationship('Team', back_populates='members')
    user = relationship('User', back_populates='team_memberships')


class DelegationTask(Base):
    __tablename__ = 'delegation_tasks'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey('teams.id'), nullable=False)
    created_by_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    brief: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_role: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(50), default='portal', nullable=False)
    status: Mapped[str] = mapped_column(String(50), default='open', nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    team = relationship('Team', back_populates='delegations')
    created_by = relationship('User', back_populates='created_delegations')


class TelegramBridgeEvent(Base):
    __tablename__ = 'telegram_bridge_events'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey('teams.id'), nullable=True)
    chat_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    user_handle: Mapped[str | None] = mapped_column(String(128), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_action: Mapped[str] = mapped_column(String(50), default='message', nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class Campaign(Base):
    __tablename__ = 'campaigns'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey('teams.id'), nullable=False)
    created_by_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    platform: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default='planning', nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    team = relationship('Team', back_populates='campaigns')
    created_by = relationship('User', back_populates='created_campaigns')
    content_items = relationship('ContentItem', back_populates='campaign', cascade='all, delete-orphan')


class ContentItem(Base):
    __tablename__ = 'content_items'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey('campaigns.id'), nullable=False)
    created_by_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    channel: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    draft: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default='draft', nullable=False)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    campaign = relationship('Campaign', back_populates='content_items')
    created_by = relationship('User', back_populates='created_content_items')
    metrics = relationship('ContentMetric', back_populates='content_item', cascade='all, delete-orphan')
    publish_jobs = relationship('PublishJob', back_populates='content_item', cascade='all, delete-orphan')


class ContentMetric(Base):
    __tablename__ = 'content_metrics'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    content_item_id: Mapped[int] = mapped_column(ForeignKey('content_items.id'), nullable=False)
    created_by_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    impressions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    likes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    comments: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    shares: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    content_item = relationship('ContentItem', back_populates='metrics')
    created_by = relationship('User', back_populates='created_metrics')


class PublishJob(Base):
    __tablename__ = 'publish_jobs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey('teams.id'), nullable=False)
    campaign_id: Mapped[int] = mapped_column(ForeignKey('campaigns.id'), nullable=False)
    content_item_id: Mapped[int] = mapped_column(ForeignKey('content_items.id'), nullable=False)
    created_by_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default='queued', nullable=False)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    team = relationship('Team', back_populates='publish_jobs')
    campaign = relationship('Campaign')
    content_item = relationship('ContentItem', back_populates='publish_jobs')
    created_by = relationship('User', back_populates='created_publish_jobs')


class Brand(Base):
    __tablename__ = 'brands'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    channels_json: Mapped[str] = mapped_column(Text, default='[]', nullable=False)
    status: Mapped[str] = mapped_column(String(50), default='draft', nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    owner = relationship('User', back_populates='brands')
    onboarding = relationship('OnboardingProfile', back_populates='brand', uselist=False, cascade='all, delete-orphan')


class OnboardingProfile(Base):
    __tablename__ = 'onboarding_profiles'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey('brands.id'), unique=True, nullable=False)
    audience: Mapped[str | None] = mapped_column(Text, nullable=True)
    tone: Mapped[str | None] = mapped_column(Text, nullable=True)
    goals: Mapped[str | None] = mapped_column(Text, nullable=True)
    assets: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    brand = relationship('Brand', back_populates='onboarding')
