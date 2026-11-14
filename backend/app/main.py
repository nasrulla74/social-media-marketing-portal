import json
import os
import re
import threading
from datetime import datetime
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .db import Base, SessionLocal, engine, get_db
from .models import Brand, Campaign, ContentItem, ContentMetric, DelegationTask, OnboardingProfile, PublishJob, Team, TeamMember, TelegramBridgeEvent, User
from .schemas import (
    AuthOut,
    BrandCreate,
    BrandOut,
    CampaignAnalyticsOut,
    CampaignCreateIn,
    CampaignOut,
    CampaignUpdateIn,
    ContentCreateIn,
    ContentMetricCreateIn,
    ContentMetricOut,
    ContentMetricSummary,
    ContentOut,
    ContentUpdateIn,
    DelegationCreateIn,
    DelegationOut,
    DelegationUpdateIn,
    LoginIn,
    MeOut,
    OnboardingIn,
    OnboardingOut,
    PublishJobCreateIn,
    PublishJobOut,
    PublishJobUpdateIn,
    RegisterIn,
    TeamCreateIn,
    TeamMemberAddIn,
    TeamMemberOut,
    TeamOut,
    TelegramInboundIn,
    TelegramInboundOut,
)
from .security import create_session, get_user_by_token, hash_password, verify_password
from .social_publish import PublishError, publish_content, provider_status

app = FastAPI(title='Social Media Marketing Portal API')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


def bridge_token_expected() -> str:
    return os.getenv('TELEGRAM_BRIDGE_TOKEN', 'change-me')


def default_telegram_team_id() -> int | None:
    raw = os.getenv('DEFAULT_TELEGRAM_TEAM_ID', '').strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


publish_worker_stop = threading.Event()
publish_worker_thread: threading.Thread | None = None


def process_publish_jobs(db: Session | None = None) -> int:
    owns_session = db is None
    session = db or SessionLocal()
    processed = 0
    try:
        now = datetime.utcnow()
        jobs = (
            session.query(PublishJob)
            .filter(
                PublishJob.status.in_(['queued', 'scheduled']),
                ((PublishJob.scheduled_for.is_(None)) | (PublishJob.scheduled_for <= now)),
            )
            .order_by(PublishJob.created_at.asc())
            .all()
        )
        for job in jobs:
            try:
                publish_content(job.content_item.channel, job.content_item.title, job.content_item.draft)
            except PublishError as exc:
                job.attempts += 1
                job.status = 'failed'
                job.last_error = str(exc)
                continue
            job.attempts += 1
            job.status = 'sent'
            job.published_at = now
            job.last_error = None
            if job.content_item and job.content_item.status in {'approved', 'scheduled'}:
                job.content_item.status = 'posted'
            processed += 1
        if processed:
            session.commit()
        else:
            session.commit()
        return processed
    except Exception:
        session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


def publish_worker_loop() -> None:
    interval = max(5, int(os.getenv('PUBLISH_WORKER_INTERVAL_SECONDS', '15')))
    while not publish_worker_stop.is_set():
        try:
            process_publish_jobs()
        except Exception:
            pass
        publish_worker_stop.wait(interval)


@app.on_event('startup')
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    global publish_worker_thread
    if publish_worker_thread is None or not publish_worker_thread.is_alive():
        publish_worker_stop.clear()
        publish_worker_thread = threading.Thread(target=publish_worker_loop, name='publish-worker', daemon=True)
        publish_worker_thread.start()


@app.on_event('shutdown')
def shutdown() -> None:
    publish_worker_stop.set()
    global publish_worker_thread
    if publish_worker_thread and publish_worker_thread.is_alive():
        publish_worker_thread.join(timeout=5)


def current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Missing token')
    token = authorization.split(' ', 1)[1].strip()
    user = get_user_by_token(db, token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token')
    return user


def team_member_role(db: Session, team_id: int, user_id: int) -> str | None:
    membership = db.query(TeamMember).filter(TeamMember.team_id == team_id, TeamMember.user_id == user_id).first()
    return membership.role if membership else None


def require_team_manager(db: Session, team_id: int, user_id: int) -> None:
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail='Team not found')
    if team.owner_id == user_id:
        return
    role = team_member_role(db, team_id, user_id)
    if role not in {'manager', 'owner'}:
        raise HTTPException(status_code=403, detail='Manager access required')


def parse_delegate_text(text: str) -> tuple[str, str, str, str]:
    command = text.strip()
    if command.startswith('/'):
        command = command[1:]
    if not command.lower().startswith('delegate'):
        raise ValueError('Not a delegate command')
    rest = command[len('delegate'):].strip()
    opts = {}
    free = []
    matches = list(re.finditer(r'(\w+)=', rest))
    if not matches:
        free = rest.split()
    else:
        prefix = rest[:matches[0].start()].strip()
        if prefix:
            free.extend(prefix.split())
        for idx, match in enumerate(matches):
            key = match.group(1).lower()
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(rest)
            value = rest[start:end].strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                value = value[1:-1]
            opts[key] = value.strip()
    team = opts.get('team') or opts.get('team_id')
    role = opts.get('role', 'agent')
    title = opts.get('title') or ' '.join(free) or 'Telegram delegation'
    brief = opts.get('brief') or None
    if not team:
        raise ValueError('team is required')
    return team, role, title, brief or ''


def serialize_campaign(row: Campaign) -> CampaignOut:
    return CampaignOut(
        id=row.id,
        team_id=row.team_id,
        created_by_id=row.created_by_id,
        name=row.name,
        goal=row.goal,
        platform=row.platform,
        status=row.status,
    )


def serialize_content(row: ContentItem) -> ContentOut:
    return ContentOut(
        id=row.id,
        campaign_id=row.campaign_id,
        created_by_id=row.created_by_id,
        channel=row.channel,
        title=row.title,
        draft=row.draft,
        status=row.status,
        scheduled_for=row.scheduled_for,
    )


def serialize_metric(row: ContentMetric) -> ContentMetricOut:
    return ContentMetricOut(
        id=row.id,
        content_item_id=row.content_item_id,
        created_by_id=row.created_by_id,
        impressions=row.impressions,
        clicks=row.clicks,
        likes=row.likes,
        comments=row.comments,
        shares=row.shares,
        recorded_at=row.recorded_at,
    )


def serialize_publish_job(row: PublishJob) -> PublishJobOut:
    return PublishJobOut(
        id=row.id,
        team_id=row.team_id,
        campaign_id=row.campaign_id,
        content_item_id=row.content_item_id,
        created_by_id=row.created_by_id,
        status=row.status,
        scheduled_for=row.scheduled_for,
        attempts=row.attempts,
        last_error=row.last_error,
        published_at=row.published_at,
    )


@app.get('/health')
def health() -> dict:
    return {'ok': True}


@app.get('/')
def root() -> dict:
    return {'service': 'api', 'status': 'ready'}


@app.get('/integrations/social/status')
def social_integration_status(user: User = Depends(current_user)):
    return provider_status()


@app.post('/auth/register', response_model=AuthOut)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=409, detail='Email already registered')
    user = User(email=email, name=payload.name.strip(), password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_session(db, user)
    return AuthOut(token=token, user_id=user.id, email=user.email, name=user.name)


@app.post('/auth/login', response_model=AuthOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail='Invalid credentials')
    token = create_session(db, user)
    return AuthOut(token=token, user_id=user.id, email=user.email, name=user.name)


@app.get('/me', response_model=MeOut)
def me(user: User = Depends(current_user)):
    return MeOut(id=user.id, email=user.email, name=user.name, role=user.role)


@app.get('/brands', response_model=list[BrandOut])
def list_brands(user: User = Depends(current_user), db: Session = Depends(get_db)):
    brands = db.query(Brand).filter(Brand.owner_id == user.id).order_by(Brand.created_at.desc()).all()
    return [
        BrandOut(
            id=brand.id,
            name=brand.name,
            website=brand.website,
            channels=json.loads(brand.channels_json or '[]'),
            status=brand.status,
            approved=brand.approved,
            notes=brand.notes,
        )
        for brand in brands
    ]


@app.post('/brands', response_model=BrandOut)
def create_brand(payload: BrandCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    brand = Brand(
        owner_id=user.id,
        name=payload.name.strip(),
        website=(payload.website or '').strip() or None,
        channels_json=json.dumps(payload.channels or []),
        notes=payload.notes,
        status='draft',
        approved=False,
    )
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return BrandOut(
        id=brand.id,
        name=brand.name,
        website=brand.website,
        channels=json.loads(brand.channels_json or '[]'),
        status=brand.status,
        approved=brand.approved,
        notes=brand.notes,
    )


@app.get('/brands/{brand_id}/onboarding', response_model=OnboardingOut)
def get_onboarding(brand_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    brand = db.query(Brand).filter(Brand.id == brand_id, Brand.owner_id == user.id).first()
    if not brand:
        raise HTTPException(status_code=404, detail='Brand not found')
    onboarding = brand.onboarding
    if not onboarding:
        return OnboardingOut(brand_id=brand.id)
    return OnboardingOut(
        brand_id=brand.id,
        audience=onboarding.audience,
        tone=onboarding.tone,
        goals=onboarding.goals,
        assets=onboarding.assets,
        approval_notes=onboarding.approval_notes,
    )


@app.post('/brands/{brand_id}/onboarding', response_model=OnboardingOut)
def set_onboarding(brand_id: int, payload: OnboardingIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    brand = db.query(Brand).filter(Brand.id == brand_id, Brand.owner_id == user.id).first()
    if not brand:
        raise HTTPException(status_code=404, detail='Brand not found')
    onboarding = brand.onboarding
    if onboarding is None:
        onboarding = OnboardingProfile(brand_id=brand.id)
        db.add(onboarding)
    onboarding.audience = payload.audience
    onboarding.tone = payload.tone
    onboarding.goals = payload.goals
    onboarding.assets = payload.assets
    onboarding.approval_notes = payload.approval_notes
    brand.status = 'onboarding_complete'
    db.commit()
    db.refresh(onboarding)
    return OnboardingOut(
        brand_id=brand.id,
        audience=onboarding.audience,
        tone=onboarding.tone,
        goals=onboarding.goals,
        assets=onboarding.assets,
        approval_notes=onboarding.approval_notes,
    )


@app.get('/teams', response_model=list[TeamOut])
def list_teams(user: User = Depends(current_user), db: Session = Depends(get_db)):
    owned = db.query(Team).filter(Team.owner_id == user.id)
    member_teams = db.query(Team).join(TeamMember).filter(TeamMember.user_id == user.id)
    seen = {}
    for team in list(owned.all()) + list(member_teams.all()):
        seen[team.id] = TeamOut(id=team.id, name=team.name, description=team.description, owner_id=team.owner_id)
    return list(seen.values())


@app.post('/teams', response_model=TeamOut)
def create_team(payload: TeamCreateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    team = Team(owner_id=user.id, name=payload.name.strip(), description=payload.description)
    db.add(team)
    db.commit()
    db.refresh(team)
    db.add(TeamMember(team_id=team.id, user_id=user.id, role='manager'))
    db.commit()
    return TeamOut(id=team.id, name=team.name, description=team.description, owner_id=team.owner_id)


@app.post('/teams/{team_id}/members', response_model=TeamMemberOut)
def add_team_member(team_id: int, payload: TeamMemberAddIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_team_manager(db, team_id, user.id)
    member_user = db.query(User).filter(User.email == payload.email.strip().lower()).first()
    if not member_user:
        raise HTTPException(status_code=404, detail='User not found')
    existing = db.query(TeamMember).filter(TeamMember.team_id == team_id, TeamMember.user_id == member_user.id).first()
    if existing:
        existing.role = payload.role
        db.commit()
        db.refresh(existing)
        return TeamMemberOut(id=existing.id, team_id=existing.team_id, user_id=existing.user_id, name=member_user.name, email=member_user.email, role=existing.role)
    membership = TeamMember(team_id=team_id, user_id=member_user.id, role=payload.role)
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return TeamMemberOut(id=membership.id, team_id=membership.team_id, user_id=membership.user_id, name=member_user.name, email=member_user.email, role=membership.role)


@app.get('/teams/{team_id}/members', response_model=list[TeamMemberOut])
def list_team_members(team_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_team_manager(db, team_id, user.id)
    rows = db.query(TeamMember).filter(TeamMember.team_id == team_id).all()
    out = []
    for row in rows:
        member_user = db.query(User).filter(User.id == row.user_id).first()
        out.append(TeamMemberOut(id=row.id, team_id=row.team_id, user_id=row.user_id, name=member_user.name, email=member_user.email, role=row.role))
    return out


@app.post('/teams/{team_id}/delegations', response_model=DelegationOut)
def create_delegation(team_id: int, payload: DelegationCreateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_team_manager(db, team_id, user.id)
    item = DelegationTask(
        team_id=team_id,
        created_by_id=user.id,
        title=payload.title.strip(),
        brief=payload.brief,
        assigned_role=payload.assigned_role.strip(),
        source='portal',
        status='open',
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return DelegationOut(
        id=item.id,
        team_id=item.team_id,
        created_by_id=item.created_by_id,
        title=item.title,
        brief=item.brief,
        assigned_role=item.assigned_role,
        source=item.source,
        status=item.status,
    )


@app.get('/teams/{team_id}/delegations', response_model=list[DelegationOut])
def list_delegations(team_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_team_manager(db, team_id, user.id)
    rows = db.query(DelegationTask).filter(DelegationTask.team_id == team_id).order_by(DelegationTask.created_at.desc()).all()
    return [
        DelegationOut(
            id=row.id,
            team_id=row.team_id,
            created_by_id=row.created_by_id,
            title=row.title,
            brief=row.brief,
            assigned_role=row.assigned_role,
            source=row.source,
            status=row.status,
        )
        for row in rows
    ]


@app.patch('/teams/{team_id}/delegations/{task_id}', response_model=DelegationOut)
def update_delegation(team_id: int, task_id: int, payload: DelegationUpdateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_team_manager(db, team_id, user.id)
    item = db.query(DelegationTask).filter(DelegationTask.id == task_id, DelegationTask.team_id == team_id).first()
    if not item:
        raise HTTPException(status_code=404, detail='Task not found')
    if payload.status is not None:
        item.status = payload.status
    if payload.brief is not None:
        item.brief = payload.brief
    if payload.source is not None:
        item.source = payload.source
    db.commit()
    db.refresh(item)
    return DelegationOut(
        id=item.id,
        team_id=item.team_id,
        created_by_id=item.created_by_id,
        title=item.title,
        brief=item.brief,
        assigned_role=item.assigned_role,
        source=item.source,
        status=item.status,
    )


@app.get('/teams/{team_id}/campaigns', response_model=list[CampaignOut])
def list_campaigns(team_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_team_manager(db, team_id, user.id)
    rows = db.query(Campaign).filter(Campaign.team_id == team_id).order_by(Campaign.created_at.desc()).all()
    return [serialize_campaign(row) for row in rows]


@app.post('/teams/{team_id}/campaigns', response_model=CampaignOut)
def create_campaign(team_id: int, payload: CampaignCreateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_team_manager(db, team_id, user.id)
    row = Campaign(
        team_id=team_id,
        created_by_id=user.id,
        name=payload.name.strip(),
        goal=payload.goal,
        platform=payload.platform,
        status='planning',
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_campaign(row)


@app.patch('/teams/{team_id}/campaigns/{campaign_id}', response_model=CampaignOut)
def update_campaign(team_id: int, campaign_id: int, payload: CampaignUpdateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_team_manager(db, team_id, user.id)
    row = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.team_id == team_id).first()
    if not row:
        raise HTTPException(status_code=404, detail='Campaign not found')
    if payload.status is not None:
        row.status = payload.status
    if payload.goal is not None:
        row.goal = payload.goal
    if payload.platform is not None:
        row.platform = payload.platform
    db.commit()
    db.refresh(row)
    return serialize_campaign(row)


@app.get('/teams/{team_id}/campaigns/{campaign_id}/content', response_model=list[ContentOut])
def list_content_items(team_id: int, campaign_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_team_manager(db, team_id, user.id)
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.team_id == team_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail='Campaign not found')
    rows = db.query(ContentItem).filter(ContentItem.campaign_id == campaign_id).order_by(ContentItem.created_at.desc()).all()
    return [serialize_content(row) for row in rows]


@app.post('/teams/{team_id}/campaigns/{campaign_id}/content', response_model=ContentOut)
def create_content_item(team_id: int, campaign_id: int, payload: ContentCreateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_team_manager(db, team_id, user.id)
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.team_id == team_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail='Campaign not found')
    row = ContentItem(
        campaign_id=campaign_id,
        created_by_id=user.id,
        channel=payload.channel.strip(),
        title=payload.title.strip(),
        draft=payload.draft,
        status=payload.status,
        scheduled_for=payload.scheduled_for,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_content(row)


@app.patch('/teams/{team_id}/campaigns/{campaign_id}/content/{content_id}', response_model=ContentOut)
def update_content_item(team_id: int, campaign_id: int, content_id: int, payload: ContentUpdateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_team_manager(db, team_id, user.id)
    row = db.query(ContentItem).filter(ContentItem.id == content_id, ContentItem.campaign_id == campaign_id).first()
    if not row:
        raise HTTPException(status_code=404, detail='Content item not found')
    if payload.channel is not None:
        row.channel = payload.channel
    if payload.title is not None:
        row.title = payload.title
    if payload.draft is not None:
        row.draft = payload.draft
    if payload.status is not None:
        row.status = payload.status
    if payload.scheduled_for is not None:
        row.scheduled_for = payload.scheduled_for
    db.commit()
    db.refresh(row)
    return serialize_content(row)


@app.post('/teams/{team_id}/campaigns/{campaign_id}/content/{content_id}/metrics', response_model=ContentMetricOut)
def add_content_metric(team_id: int, campaign_id: int, content_id: int, payload: ContentMetricCreateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_team_manager(db, team_id, user.id)
    item = db.query(ContentItem).join(Campaign).filter(ContentItem.id == content_id, Campaign.id == campaign_id, Campaign.team_id == team_id).first()
    if not item:
        raise HTTPException(status_code=404, detail='Content item not found')
    row = ContentMetric(
        content_item_id=content_id,
        created_by_id=user.id,
        impressions=payload.impressions,
        clicks=payload.clicks,
        likes=payload.likes,
        comments=payload.comments,
        shares=payload.shares,
        recorded_at=payload.recorded_at or datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_metric(row)


@app.get('/teams/{team_id}/campaigns/{campaign_id}/analytics', response_model=CampaignAnalyticsOut)
def campaign_analytics(team_id: int, campaign_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_team_manager(db, team_id, user.id)
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.team_id == team_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail='Campaign not found')
    items = db.query(ContentItem).filter(ContentItem.campaign_id == campaign_id).all()
    summaries: list[ContentMetricSummary] = []
    totals = {'impressions': 0, 'clicks': 0, 'likes': 0, 'comments': 0, 'shares': 0}
    for item in items:
        metrics = db.query(ContentMetric).filter(ContentMetric.content_item_id == item.id).all()
        item_totals = {'impressions': 0, 'clicks': 0, 'likes': 0, 'comments': 0, 'shares': 0}
        for metric in metrics:
            item_totals['impressions'] += metric.impressions or 0
            item_totals['clicks'] += metric.clicks or 0
            item_totals['likes'] += metric.likes or 0
            item_totals['comments'] += metric.comments or 0
            item_totals['shares'] += metric.shares or 0
        for key in totals:
            totals[key] += item_totals[key]
        summaries.append(
            ContentMetricSummary(
                content_item_id=item.id,
                title=item.title,
                channel=item.channel,
                status=item.status,
                impressions=item_totals['impressions'],
                clicks=item_totals['clicks'],
                likes=item_totals['likes'],
                comments=item_totals['comments'],
                shares=item_totals['shares'],
            )
        )
    return CampaignAnalyticsOut(campaign_id=campaign.id, content_count=len(items), totals=totals, items=summaries)


@app.post('/teams/{team_id}/campaigns/{campaign_id}/content/{content_id}/publish', response_model=PublishJobOut)
def queue_publish(team_id: int, campaign_id: int, content_id: int, payload: PublishJobCreateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_team_manager(db, team_id, user.id)
    item = db.query(ContentItem).join(Campaign).filter(ContentItem.id == content_id, Campaign.id == campaign_id, Campaign.team_id == team_id).first()
    if not item:
        raise HTTPException(status_code=404, detail='Content item not found')
    if item.status not in {'approved', 'scheduled'}:
        raise HTTPException(status_code=409, detail='Content must be approved or scheduled before publishing')
    job = PublishJob(
        team_id=team_id,
        campaign_id=campaign_id,
        content_item_id=content_id,
        created_by_id=user.id,
        status='scheduled' if payload.scheduled_for or item.scheduled_for else 'queued',
        scheduled_for=payload.scheduled_for or item.scheduled_for,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return serialize_publish_job(job)


@app.get('/teams/{team_id}/publish-queue', response_model=list[PublishJobOut])
def list_publish_queue(team_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_team_manager(db, team_id, user.id)
    rows = db.query(PublishJob).filter(PublishJob.team_id == team_id).order_by(PublishJob.created_at.desc()).all()
    return [serialize_publish_job(row) for row in rows]


@app.patch('/teams/{team_id}/publish-queue/{job_id}', response_model=PublishJobOut)
def update_publish_job(team_id: int, job_id: int, payload: PublishJobUpdateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_team_manager(db, team_id, user.id)
    job = db.query(PublishJob).filter(PublishJob.id == job_id, PublishJob.team_id == team_id).first()
    if not job:
        raise HTTPException(status_code=404, detail='Publish job not found')
    if payload.status is not None:
        job.status = payload.status
        if payload.status == 'sent':
            job.published_at = payload.published_at or datetime.utcnow()
    if payload.attempts is not None:
        job.attempts = payload.attempts
    if payload.last_error is not None:
        job.last_error = payload.last_error
    if payload.published_at is not None:
        job.published_at = payload.published_at
    if payload.scheduled_for is not None:
        job.scheduled_for = payload.scheduled_for
    db.commit()
    db.refresh(job)
    return serialize_publish_job(job)


@app.post('/integrations/telegram/inbound', response_model=TelegramInboundOut)
def telegram_inbound(payload: TelegramInboundIn, x_bridge_token: str | None = Header(default=None), db: Session = Depends(get_db)):
    if x_bridge_token != bridge_token_expected():
        raise HTTPException(status_code=401, detail='Invalid bridge token')
    return dispatch_telegram_event(
        team_id=payload.team_id,
        chat_id=payload.chat_id,
        user_handle=payload.user_handle,
        text=payload.text,
        db=db,
    )


def dispatch_telegram_event(*, team_id: int, chat_id: str | None, user_handle: str | None, text: str, db: Session) -> TelegramInboundOut:
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail='Team not found')

    parsed_action = 'message'
    task_id = None
    text = text.strip()
    db.add(
        TelegramBridgeEvent(
            team_id=team.id,
            chat_id=chat_id,
            user_handle=user_handle,
            raw_text=text,
            parsed_action=parsed_action,
        )
    )

    if text.lower().startswith('/delegate'):
        try:
            _, role, title, brief = parse_delegate_text(text)
            item = DelegationTask(
                team_id=team.id,
                created_by_id=team.owner_id,
                title=title,
                brief=brief or None,
                assigned_role=role,
                source='telegram',
                status='open',
            )
            db.add(item)
            db.flush()
            task_id = item.id
            parsed_action = 'delegate'
            db.add(
                TelegramBridgeEvent(
                    team_id=team.id,
                    chat_id=chat_id,
                    user_handle=user_handle,
                    raw_text=text,
                    parsed_action=parsed_action,
                )
            )
        except Exception as exc:
            parsed_action = 'error'
            db.add(
                TelegramBridgeEvent(
                    team_id=team.id,
                    chat_id=chat_id,
                    user_handle=user_handle,
                    raw_text=f'{text} :: parse_error={exc}',
                    parsed_action=parsed_action,
                )
            )
            db.commit()
            return TelegramInboundOut(accepted=True, parsed_action=parsed_action, task_id=None, message='Stored Telegram event; command parse failed')

    db.commit()
    return TelegramInboundOut(accepted=True, parsed_action=parsed_action, task_id=task_id, message='Telegram event accepted')


@app.post('/integrations/telegram/webhook', response_model=TelegramInboundOut)
def telegram_webhook(payload: dict, x_telegram_bot_api_secret_token: str | None = Header(default=None), db: Session = Depends(get_db)):
    if x_telegram_bot_api_secret_token != bridge_token_expected():
        raise HTTPException(status_code=401, detail='Invalid bridge token')
    team_id = default_telegram_team_id()
    if team_id is None:
        raise HTTPException(status_code=400, detail='DEFAULT_TELEGRAM_TEAM_ID is not configured')
    message = payload.get('message') or {}
    text = str(message.get('text') or '').strip()
    if not text:
        return TelegramInboundOut(accepted=True, parsed_action='message', task_id=None, message='No text message found')
    chat = message.get('chat') or {}
    frm = message.get('from') or {}
    chat_id = str(chat.get('id') or '') or None
    user_handle = frm.get('username') or frm.get('first_name') or None
    return dispatch_telegram_event(team_id=team_id, chat_id=chat_id, user_handle=user_handle, text=text, db=db)


@app.get('/integrations/telegram/events')
def telegram_events(user: User = Depends(current_user), db: Session = Depends(get_db)):
    team_ids = [row[0] for row in db.query(Team.id).filter(Team.owner_id == user.id).all()]
    if not team_ids:
        return []
    events = db.query(TelegramBridgeEvent).filter(TelegramBridgeEvent.team_id.in_(team_ids)).order_by(TelegramBridgeEvent.created_at.desc()).limit(50).all()
    return [
        {
            'id': ev.id,
            'team_id': ev.team_id,
            'chat_id': ev.chat_id,
            'user_handle': ev.user_handle,
            'raw_text': ev.raw_text,
            'parsed_action': ev.parsed_action,
            'created_at': ev.created_at.isoformat(),
        }
        for ev in events
    ]
