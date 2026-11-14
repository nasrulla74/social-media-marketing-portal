'use client';

import { useEffect, useMemo, useState } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

type Brand = { id: number; name: string; website?: string | null; channels: string[]; status: string; approved: boolean; notes?: string | null };
type Team = { id: number; name: string; description?: string | null; owner_id: number };
type TeamMember = { id: number; team_id: number; user_id: number; name: string; email: string; role: string };
type Delegation = { id: number; team_id: number; created_by_id: number; title: string; brief?: string | null; assigned_role: string; source: string; status: string };
type TelegramEvent = { id: number; team_id: number | null; chat_id?: string | null; user_handle?: string | null; raw_text: string; parsed_action: string; created_at: string };
type Campaign = { id: number; team_id: number; created_by_id: number; name: string; goal?: string | null; platform?: string | null; status: string };
type ContentItem = { id: number; campaign_id: number; created_by_id: number; channel: string; title: string; draft?: string | null; status: string; scheduled_for?: string | null };
type AnalyticsSummary = { campaign_id: number; content_count: number; totals: { impressions: number; clicks: number; likes: number; comments: number; shares: number }; items: Array<{ content_item_id: number; title: string; channel: string; status: string; impressions: number; clicks: number; likes: number; comments: number; shares: number }> };
type PublishJob = { id: number; team_id: number; campaign_id: number; content_item_id: number; created_by_id: number; status: string; scheduled_for?: string | null; attempts: number; last_error?: string | null; published_at?: string | null };

export default function Page() {
  const [mode, setMode] = useState<'login' | 'register'>('register');
  const [token, setToken] = useState<string | null>(null);
  const [me, setMe] = useState<{ id: number; email: string; name: string; role: string } | null>(null);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [delegations, setDelegations] = useState<Delegation[]>([]);
  const [telegramEvents, setTelegramEvents] = useState<TelegramEvent[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [contentItems, setContentItems] = useState<ContentItem[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null);
  const [publishQueue, setPublishQueue] = useState<PublishJob[]>([]);
  const [auth, setAuth] = useState({ email: '', password: '', name: '' });
  const [brandForm, setBrandForm] = useState({ name: '', website: '', channels: 'Telegram, X, LinkedIn', notes: '' });
  const [onboarding, setOnboarding] = useState({ audience: '', tone: '', goals: '', assets: '', approval_notes: '' });
  const [teamForm, setTeamForm] = useState({ name: '', description: '' });
  const [memberForm, setMemberForm] = useState({ email: '', role: 'agent' });
  const [delegationForm, setDelegationForm] = useState({ title: '', brief: '', assigned_role: 'copywriter' });
  const [campaignForm, setCampaignForm] = useState({ name: '', goal: '', platform: '' });
  const [contentForm, setContentForm] = useState({ channel: 'Instagram', title: '', draft: '', status: 'draft', scheduled_for: '' });
  const [metricsForm, setMetricsForm] = useState({ impressions: '0', clicks: '0', likes: '0', comments: '0', shares: '0', recorded_for: '' });
  const [publishForm, setPublishForm] = useState({ scheduled_for: '' });
  const [selectedBrandId, setSelectedBrandId] = useState<number | null>(null);
  const [selectedTeamId, setSelectedTeamId] = useState<number | null>(null);
  const [selectedCampaignId, setSelectedCampaignId] = useState<number | null>(null);
  const [selectedContentId, setSelectedContentId] = useState<number | null>(null);
  const [message, setMessage] = useState('');

  useEffect(() => {
    const saved = localStorage.getItem('smp_token');
    if (saved) setToken(saved);
  }, []);

  useEffect(() => {
    if (!token) return;
    localStorage.setItem('smp_token', token);
    void refreshMe(token);
    void refreshBrands(token);
    void refreshTeams(token);
    void refreshTelegramEvents(token);
  }, [token]);

  useEffect(() => { if (!token || !selectedBrandId) return; void loadOnboarding(token, selectedBrandId); }, [token, selectedBrandId]);
  useEffect(() => { if (!token || !selectedTeamId) return; void refreshTeamData(token, selectedTeamId); void refreshCampaigns(token, selectedTeamId); void refreshPublishQueue(token, selectedTeamId); }, [token, selectedTeamId]);
  useEffect(() => { if (!token || !selectedCampaignId || !selectedTeamId) return; void refreshContent(token, selectedTeamId, selectedCampaignId); void refreshAnalytics(token, selectedTeamId, selectedCampaignId); }, [token, selectedCampaignId, selectedTeamId]);
  useEffect(() => { if (!contentItems.length) { setSelectedContentId(null); return; } if (!selectedContentId || !contentItems.some((item) => item.id === selectedContentId)) { setSelectedContentId(contentItems[0].id); } }, [contentItems, selectedContentId]);

  const headers = useMemo(() => ({ 'Content-Type': 'application/json', Authorization: token ? `Bearer ${token}` : '' }), [token]);

  async function refreshMe(t = token) { if (!t) return; const res = await fetch(`${API_BASE}/me`, { headers: { Authorization: `Bearer ${t}` } }); if (res.ok) setMe(await res.json()); }
  async function refreshBrands(t = token) { if (!t) return; const res = await fetch(`${API_BASE}/brands`, { headers: { Authorization: `Bearer ${t}` } }); if (res.ok) { const data = await res.json(); setBrands(data); if (!selectedBrandId && data.length) setSelectedBrandId(data[0].id); } }
  async function refreshTeams(t = token) { if (!t) return; const res = await fetch(`${API_BASE}/teams`, { headers: { Authorization: `Bearer ${t}` } }); if (res.ok) { const data = await res.json(); setTeams(data); if (!selectedTeamId && data.length) setSelectedTeamId(data[0].id); } }
  async function refreshTelegramEvents(t = token) { if (!t) return; const res = await fetch(`${API_BASE}/integrations/telegram/events`, { headers: { Authorization: `Bearer ${t}` } }); if (res.ok) setTelegramEvents(await res.json()); }
  async function refreshTeamData(t: string, teamId: number) { const [membersRes, delegationsRes] = await Promise.all([fetch(`${API_BASE}/teams/${teamId}/members`, { headers: { Authorization: `Bearer ${t}` } }), fetch(`${API_BASE}/teams/${teamId}/delegations`, { headers: { Authorization: `Bearer ${t}` } })]); if (membersRes.ok) setTeamMembers(await membersRes.json()); if (delegationsRes.ok) setDelegations(await delegationsRes.json()); }
  async function refreshCampaigns(t: string, teamId: number) { const res = await fetch(`${API_BASE}/teams/${teamId}/campaigns`, { headers: { Authorization: `Bearer ${t}` } }); if (res.ok) { const data = await res.json(); setCampaigns(data); if (!selectedCampaignId && data.length) setSelectedCampaignId(data[0].id); } }
  async function refreshContent(t: string, teamId: number, campaignId: number) { const res = await fetch(`${API_BASE}/teams/${teamId}/campaigns/${campaignId}/content`, { headers: { Authorization: `Bearer ${t}` } }); if (res.ok) setContentItems(await res.json()); }
  async function refreshAnalytics(t: string, teamId: number, campaignId: number) { const res = await fetch(`${API_BASE}/teams/${teamId}/campaigns/${campaignId}/analytics`, { headers: { Authorization: `Bearer ${t}` } }); if (res.ok) setAnalytics(await res.json()); }
  async function refreshPublishQueue(t: string, teamId: number) { const res = await fetch(`${API_BASE}/teams/${teamId}/publish-queue`, { headers: { Authorization: `Bearer ${t}` } }); if (res.ok) setPublishQueue(await res.json()); }

  async function loadOnboarding(t: string, id: number) { const res = await fetch(`${API_BASE}/brands/${id}/onboarding`, { headers: { Authorization: `Bearer ${t}` } }); if (res.ok) { const data = await res.json(); setOnboarding({ audience: data.audience || '', tone: data.tone || '', goals: data.goals || '', assets: data.assets || '', approval_notes: data.approval_notes || '' }); } }

  async function submitAuth() { setMessage(''); const endpoint = mode === 'register' ? '/auth/register' : '/auth/login'; const body = mode === 'register' ? { ...auth } : { email: auth.email, password: auth.password }; const res = await fetch(`${API_BASE}${endpoint}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }); const data = await res.json(); if (!res.ok) { setMessage(data.detail || 'Authentication failed'); return; } setToken(data.token); setMessage(`Signed in as ${data.name}`); }

  async function createBrand() { if (!token) return; setMessage(''); const res = await fetch(`${API_BASE}/brands`, { method: 'POST', headers, body: JSON.stringify({ name: brandForm.name, website: brandForm.website, channels: brandForm.channels.split(',').map((s) => s.trim()).filter(Boolean), notes: brandForm.notes }) }); const data = await res.json(); if (!res.ok) { setMessage(data.detail || 'Unable to create brand'); return; } setMessage(`Created brand ${data.name}`); await refreshBrands(token); setSelectedBrandId(data.id); }
  async function saveOnboarding() { if (!token || !selectedBrandId) return; const res = await fetch(`${API_BASE}/brands/${selectedBrandId}/onboarding`, { method: 'POST', headers, body: JSON.stringify(onboarding) }); const data = await res.json(); if (!res.ok) { setMessage(data.detail || 'Unable to save onboarding'); return; } setMessage('Onboarding saved. Brand marked ready for review.'); await refreshBrands(token); }
  async function createTeam() { if (!token) return; setMessage(''); const res = await fetch(`${API_BASE}/teams`, { method: 'POST', headers, body: JSON.stringify(teamForm) }); const data = await res.json(); if (!res.ok) { setMessage(data.detail || 'Unable to create team'); return; } setMessage(`Created team ${data.name}`); await refreshTeams(token); setSelectedTeamId(data.id); }
  async function addMember() { if (!token || !selectedTeamId) return; setMessage(''); const res = await fetch(`${API_BASE}/teams/${selectedTeamId}/members`, { method: 'POST', headers, body: JSON.stringify(memberForm) }); const data = await res.json(); if (!res.ok) { setMessage(data.detail || 'Unable to add member'); return; } setMessage(`Added ${data.name} to team`); await refreshTeamData(token, selectedTeamId); }
  async function createDelegation() { if (!token || !selectedTeamId) return; setMessage(''); const res = await fetch(`${API_BASE}/teams/${selectedTeamId}/delegations`, { method: 'POST', headers, body: JSON.stringify(delegationForm) }); const data = await res.json(); if (!res.ok) { setMessage(data.detail || 'Unable to create delegation'); return; } setMessage(`Delegation created: ${data.title}`); await refreshTeamData(token, selectedTeamId); }
  async function patchDelegation(taskId: number, status: string) { if (!token || !selectedTeamId) return; const res = await fetch(`${API_BASE}/teams/${selectedTeamId}/delegations/${taskId}`, { method: 'PATCH', headers, body: JSON.stringify({ status }) }); const data = await res.json(); if (!res.ok) { setMessage(data.detail || 'Unable to update delegation'); return; } setDelegations((curr) => curr.map((item) => (item.id === taskId ? data : item))); setMessage(`Updated delegation: ${data.title}`); }
  async function createCampaign() { if (!token || !selectedTeamId) return; setMessage(''); const res = await fetch(`${API_BASE}/teams/${selectedTeamId}/campaigns`, { method: 'POST', headers, body: JSON.stringify(campaignForm) }); const data = await res.json(); if (!res.ok) { setMessage(data.detail || 'Unable to create campaign'); return; } setMessage(`Created campaign ${data.name}`); await refreshCampaigns(token, selectedTeamId); setSelectedCampaignId(data.id); }
  async function createContentItem() { if (!token || !selectedTeamId || !selectedCampaignId) return; setMessage(''); const payload = { channel: contentForm.channel, title: contentForm.title, draft: contentForm.draft, status: contentForm.status, scheduled_for: contentForm.scheduled_for ? new Date(contentForm.scheduled_for).toISOString() : null }; const res = await fetch(`${API_BASE}/teams/${selectedTeamId}/campaigns/${selectedCampaignId}/content`, { method: 'POST', headers, body: JSON.stringify(payload) }); const data = await res.json(); if (!res.ok) { setMessage(data.detail || 'Unable to create content item'); return; } setMessage(`Created content item ${data.title}`); await refreshContent(token, selectedTeamId, selectedCampaignId); await refreshAnalytics(token, selectedTeamId, selectedCampaignId); }
  async function patchContentItem(itemId: number, status: string) { if (!token || !selectedTeamId || !selectedCampaignId) return; const res = await fetch(`${API_BASE}/teams/${selectedTeamId}/campaigns/${selectedCampaignId}/content/${itemId}`, { method: 'PATCH', headers, body: JSON.stringify({ status }) }); const data = await res.json(); if (!res.ok) { setMessage(data.detail || 'Unable to update content item'); return; } setContentItems((curr) => curr.map((item) => (item.id === itemId ? data : item))); setMessage(`Updated content item: ${data.title}`); await refreshAnalytics(token, selectedTeamId, selectedCampaignId); }
  async function addMetrics() { if (!token || !selectedTeamId || !selectedCampaignId || !selectedContentId) return; setMessage(''); const payload = { impressions: Number(metricsForm.impressions || 0), clicks: Number(metricsForm.clicks || 0), likes: Number(metricsForm.likes || 0), comments: Number(metricsForm.comments || 0), shares: Number(metricsForm.shares || 0), recorded_at: metricsForm.recorded_for ? new Date(metricsForm.recorded_for).toISOString() : null }; const res = await fetch(`${API_BASE}/teams/${selectedTeamId}/campaigns/${selectedCampaignId}/content/${selectedContentId}/metrics`, { method: 'POST', headers, body: JSON.stringify(payload) }); const data = await res.json(); if (!res.ok) { setMessage(data.detail || 'Unable to save metrics'); return; } setMessage('Metrics saved'); await refreshAnalytics(token, selectedTeamId, selectedCampaignId); }
  async function queuePublish() { if (!token || !selectedTeamId || !selectedCampaignId || !selectedContentId) return; setMessage(''); const payload = { scheduled_for: publishForm.scheduled_for ? new Date(publishForm.scheduled_for).toISOString() : null }; const res = await fetch(`${API_BASE}/teams/${selectedTeamId}/campaigns/${selectedCampaignId}/content/${selectedContentId}/publish`, { method: 'POST', headers, body: JSON.stringify(payload) }); const data = await res.json(); if (!res.ok) { setMessage(data.detail || 'Unable to queue publish'); return; } setMessage(`Queued publish job ${data.id}`); await refreshPublishQueue(token, selectedTeamId); }
  async function updatePublishJob(jobId: number, status: string) { if (!token || !selectedTeamId) return; const res = await fetch(`${API_BASE}/teams/${selectedTeamId}/publish-queue/${jobId}`, { method: 'PATCH', headers, body: JSON.stringify({ status }) }); const data = await res.json(); if (!res.ok) { setMessage(data.detail || 'Unable to update publish job'); return; } setPublishQueue((curr) => curr.map((job) => (job.id === jobId ? data : job))); setMessage(`Updated publish job ${jobId}`); }
  async function sendTelegramCommand() { if (!token || !selectedTeamId) return; setMessage(''); const tokenValue = prompt('Telegram bridge token') || ''; if (!tokenValue) return; const text = prompt('Telegram command (example: /delegate team=1 role=copywriter title="Write captions" brief="Weekly promo copy")') || ''; if (!text) return; const res = await fetch(`${API_BASE}/integrations/telegram/inbound`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Bridge-Token': tokenValue }, body: JSON.stringify({ team_id: selectedTeamId, chat_id: 'manual', user_handle: 'portal', text }) }); const data = await res.json(); if (!res.ok) { setMessage(data.detail || 'Telegram bridge call failed'); return; } setMessage(`${data.message} (${data.parsed_action})`); await refreshTeamData(token, selectedTeamId); await refreshTelegramEvents(token); }

  function logout() { localStorage.removeItem('smp_token'); setToken(null); setMe(null); setBrands([]); setTeams([]); setTeamMembers([]); setDelegations([]); setTelegramEvents([]); setCampaigns([]); setContentItems([]); setAnalytics(null); setPublishQueue([]); setSelectedBrandId(null); setSelectedTeamId(null); setSelectedCampaignId(null); setSelectedContentId(null); setMessage('Logged out'); }

  const selectedBrand = brands.find((b) => b.id === selectedBrandId) || null;
  const selectedTeam = teams.find((t) => t.id === selectedTeamId) || null;
  const selectedCampaign = campaigns.find((c) => c.id === selectedCampaignId) || null;

  return (
    <main>
      <span className="badge">MVP scaffold</span>
      <h1>Social Media Marketing Portal</h1>
      <p>Separate customer portal for onboarding, brand setup, team delegation, campaign planning, analytics, publishing, and approval-driven operations.</p>

      {message ? <div className="card" style={{ marginTop: 16, borderColor: '#bfdbfe', background: '#eff6ff' }}>{message}</div> : null}

      {!token ? (
        <div className="grid" style={{ marginTop: 24 }}>
          <section className="card">
            <h2>{mode === 'register' ? 'Create account' : 'Sign in'}</h2>
            {mode === 'register' && <input placeholder="Name" value={auth.name} onChange={(e) => setAuth({ ...auth, name: e.target.value })} style={inputStyle} />}
            <input placeholder="Email" value={auth.email} onChange={(e) => setAuth({ ...auth, email: e.target.value })} style={inputStyle} />
            <input type="password" placeholder="Password" value={auth.password} onChange={(e) => setAuth({ ...auth, password: e.target.value })} style={inputStyle} />
            <button onClick={submitAuth}>{mode === 'register' ? 'Register' : 'Login'}</button>
            <p style={{ marginTop: 12 }}><button onClick={() => setMode(mode === 'register' ? 'login' : 'register')} style={{ ...linkButtonStyle, padding: 0 }}>Switch to {mode === 'register' ? 'login' : 'registration'}</button></p>
          </section>

          <section className="card">
            <h2>What this portal does</h2>
            <ul>
              <li>Collect brand info and content goals</li>
              <li>Track onboarding status</li>
              <li>Support approval-gated content operations</li>
              <li>Manage internal teams, delegations, campaigns, analytics, and publishing</li>
              <li>Receive Telegram commands for delegation</li>
            </ul>
          </section>
        </div>
      ) : (
        <div style={{ marginTop: 24, display: 'grid', gap: 16 }}>
          <section className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
              <div>
                <h2 style={{ marginTop: 0 }}>Signed in</h2>
                <p>{me?.name} · {me?.email}</p>
              </div>
              <button onClick={logout} style={{ background: '#fff', color: '#2563eb' }}>Logout</button>
            </div>
          </section>

          <section className="grid">
            <section className="card">
              <h2>Create customer brand</h2>
              <input placeholder="Brand name" value={brandForm.name} onChange={(e) => setBrandForm({ ...brandForm, name: e.target.value })} style={inputStyle} />
              <input placeholder="Website" value={brandForm.website} onChange={(e) => setBrandForm({ ...brandForm, website: e.target.value })} style={inputStyle} />
              <input placeholder="Channels (comma-separated)" value={brandForm.channels} onChange={(e) => setBrandForm({ ...brandForm, channels: e.target.value })} style={inputStyle} />
              <textarea placeholder="Notes" value={brandForm.notes} onChange={(e) => setBrandForm({ ...brandForm, notes: e.target.value })} style={{ ...inputStyle, minHeight: 96 }} />
              <button onClick={createBrand}>Create brand</button>
            </section>

            <section className="card">
              <h2>Brands</h2>
              <div style={{ display: 'grid', gap: 10 }}>
                {brands.length === 0 ? <p>No brands yet.</p> : null}
                {brands.map((brand) => (<button key={brand.id} onClick={() => setSelectedBrandId(brand.id)} style={{ ...selectButtonStyle, borderColor: selectedBrandId === brand.id ? '#2563eb' : '#d1d5db', background: selectedBrandId === brand.id ? '#eff6ff' : '#fff' }}>{brand.name} · {brand.status} · {brand.approved ? 'approved' : 'pending'}</button>))}
              </div>
            </section>
          </section>

          {selectedBrand ? (
            <section className="card"><h2>Onboarding for {selectedBrand.name}</h2><p>{selectedBrand.website || 'No website set yet'}</p><div className="grid"><textarea placeholder="Audience" value={onboarding.audience} onChange={(e) => setOnboarding({ ...onboarding, audience: e.target.value })} style={inputStyle} /><textarea placeholder="Tone" value={onboarding.tone} onChange={(e) => setOnboarding({ ...onboarding, tone: e.target.value })} style={inputStyle} /><textarea placeholder="Goals" value={onboarding.goals} onChange={(e) => setOnboarding({ ...onboarding, goals: e.target.value })} style={inputStyle} /><textarea placeholder="Assets" value={onboarding.assets} onChange={(e) => setOnboarding({ ...onboarding, assets: e.target.value })} style={inputStyle} /></div><textarea placeholder="Approval notes" value={onboarding.approval_notes} onChange={(e) => setOnboarding({ ...onboarding, approval_notes: e.target.value })} style={{ ...inputStyle, minHeight: 100 }} /><button onClick={saveOnboarding}>Save onboarding</button></section>
          ) : null}

          <section className="grid">
            <section className="card"><h2>Create marketing team</h2><input placeholder="Team name" value={teamForm.name} onChange={(e) => setTeamForm({ ...teamForm, name: e.target.value })} style={inputStyle} /><textarea placeholder="Description" value={teamForm.description} onChange={(e) => setTeamForm({ ...teamForm, description: e.target.value })} style={{ ...inputStyle, minHeight: 96 }} /><button onClick={createTeam}>Create team</button></section>
            <section className="card"><h2>Teams</h2><div style={{ display: 'grid', gap: 10 }}>{teams.length === 0 ? <p>No teams yet.</p> : null}{teams.map((team) => (<button key={team.id} onClick={() => setSelectedTeamId(team.id)} style={{ ...selectButtonStyle, borderColor: selectedTeamId === team.id ? '#2563eb' : '#d1d5db', background: selectedTeamId === team.id ? '#eff6ff' : '#fff' }}>{team.name}</button>))}</div></section>
          </section>

          {selectedTeam ? (
            <section className="card">
              <h2>Team: {selectedTeam.name}</h2><p>{selectedTeam.description || 'No description'}</p>
              <div className="grid">
                <section><h3>Add member</h3><input placeholder="User email" value={memberForm.email} onChange={(e) => setMemberForm({ ...memberForm, email: e.target.value })} style={inputStyle} /><input placeholder="Role (manager / agent / client)" value={memberForm.role} onChange={(e) => setMemberForm({ ...memberForm, role: e.target.value })} style={inputStyle} /><button onClick={addMember}>Add member</button></section>
                <section><h3>Create delegation</h3><input placeholder="Task title" value={delegationForm.title} onChange={(e) => setDelegationForm({ ...delegationForm, title: e.target.value })} style={inputStyle} /><input placeholder="Assigned role" value={delegationForm.assigned_role} onChange={(e) => setDelegationForm({ ...delegationForm, assigned_role: e.target.value })} style={inputStyle} /><textarea placeholder="Brief" value={delegationForm.brief} onChange={(e) => setDelegationForm({ ...delegationForm, brief: e.target.value })} style={{ ...inputStyle, minHeight: 96 }} /><button onClick={createDelegation}>Create delegation</button></section>
              </div>

              <div className="grid" style={{ marginTop: 16 }}>
                <section className="card"><h3>Members</h3>{teamMembers.length === 0 ? <p>No members loaded yet.</p> : null}<ul>{teamMembers.map((member) => (<li key={member.id}>{member.name} ({member.email}) · {member.role}</li>))}</ul></section>
                <section className="card"><h3>Delegations</h3>{delegations.length === 0 ? <p>No delegations yet.</p> : null}<div style={{ display: 'grid', gap: 12 }}>{delegations.map((item) => (<div key={item.id} className="card" style={{ borderStyle: 'dashed' }}><strong>{item.title}</strong><div>{item.assigned_role} · {item.source} · {item.status}</div>{item.brief ? <p>{item.brief}</p> : null}<div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}><button onClick={() => patchDelegation(item.id, 'running')}>Mark running</button><button onClick={() => patchDelegation(item.id, 'done')} style={{ background: '#16a34a' }}>Mark done</button><button onClick={() => patchDelegation(item.id, 'blocked')} style={{ background: '#dc2626' }}>Mark blocked</button></div></div>))}</div></section>
              </div>

              <section className="card" style={{ marginTop: 16 }}><h3>Telegram bridge</h3><p>Use the bridge token from .env.example to send commands into the manager workflow.</p><code>/delegate team=1 role=copywriter title="Write weekly captions" brief="Weekly promo copy"</code><div style={{ marginTop: 12 }}><button onClick={sendTelegramCommand}>Send test Telegram command</button></div><div style={{ marginTop: 12 }}>{telegramEvents.length === 0 ? <p>No Telegram events yet.</p> : null}<ul>{telegramEvents.map((ev) => (<li key={ev.id}>{ev.parsed_action} · {ev.raw_text}</li>))}</ul></div></section>

              <section className="card" style={{ marginTop: 16 }}><h3>Campaigns</h3><div className="grid"><section><h4>Create campaign</h4><input placeholder="Campaign name" value={campaignForm.name} onChange={(e) => setCampaignForm({ ...campaignForm, name: e.target.value })} style={inputStyle} /><input placeholder="Goal" value={campaignForm.goal} onChange={(e) => setCampaignForm({ ...campaignForm, goal: e.target.value })} style={inputStyle} /><input placeholder="Platform" value={campaignForm.platform} onChange={(e) => setCampaignForm({ ...campaignForm, platform: e.target.value })} style={inputStyle} /><button onClick={createCampaign}>Create campaign</button></section><section><h4>Campaign list</h4><div style={{ display: 'grid', gap: 10 }}>{campaigns.length === 0 ? <p>No campaigns yet.</p> : null}{campaigns.map((campaign) => (<button key={campaign.id} onClick={() => setSelectedCampaignId(campaign.id)} style={{ ...selectButtonStyle, borderColor: selectedCampaignId === campaign.id ? '#2563eb' : '#d1d5db', background: selectedCampaignId === campaign.id ? '#eff6ff' : '#fff' }}>{campaign.name} · {campaign.status}</button>))}</div></section></div></section>

              {selectedCampaign ? (
                <section className="card" style={{ marginTop: 16 }}>
                  <h3>Campaign: {selectedCampaign.name}</h3><p>{selectedCampaign.goal || 'No goal'} · {selectedCampaign.platform || 'No platform'}</p>
                  <div className="grid"><section><h4>Create content item</h4><input placeholder="Channel" value={contentForm.channel} onChange={(e) => setContentForm({ ...contentForm, channel: e.target.value })} style={inputStyle} /><input placeholder="Title" value={contentForm.title} onChange={(e) => setContentForm({ ...contentForm, title: e.target.value })} style={inputStyle} /><textarea placeholder="Draft" value={contentForm.draft} onChange={(e) => setContentForm({ ...contentForm, draft: e.target.value })} style={{ ...inputStyle, minHeight: 96 }} /><input placeholder="Scheduled for (ISO datetime)" value={contentForm.scheduled_for} onChange={(e) => setContentForm({ ...contentForm, scheduled_for: e.target.value })} style={inputStyle} /><input placeholder="Status" value={contentForm.status} onChange={(e) => setContentForm({ ...contentForm, status: e.target.value })} style={inputStyle} /><button onClick={createContentItem}>Create content item</button></section><section><h4>Content items</h4><div style={{ display: 'grid', gap: 10 }}>{contentItems.length === 0 ? <p>No content items yet.</p> : null}{contentItems.map((item) => (<div key={item.id} className="card" style={{ borderStyle: 'dashed' }}><strong>{item.title}</strong><div>{item.channel} · {item.status}</div>{item.draft ? <p>{item.draft}</p> : null}{item.scheduled_for ? <p>Scheduled: {item.scheduled_for}</p> : null}<div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}><button onClick={() => setSelectedContentId(item.id)} style={{ background: '#0f172a' }}>Metrics</button><button onClick={() => patchContentItem(item.id, 'draft')}>Draft</button><button onClick={() => patchContentItem(item.id, 'in_review')}>In review</button><button onClick={() => patchContentItem(item.id, 'approved')} style={{ background: '#16a34a' }}>Approved</button><button onClick={() => patchContentItem(item.id, 'scheduled')} style={{ background: '#2563eb' }}>Scheduled</button><button onClick={() => patchContentItem(item.id, 'posted')} style={{ background: '#7c3aed' }}>Posted</button></div></div>))}</div></section></div>

                  <div className="grid" style={{ marginTop: 16 }}>
                    <section className="card"><h4>Save performance metrics</h4><p>Selected content item: {selectedContentId || 'none'}</p><input placeholder="Recorded at (ISO datetime optional)" value={metricsForm.recorded_for} onChange={(e) => setMetricsForm({ ...metricsForm, recorded_for: e.target.value })} style={inputStyle} /><input placeholder="Impressions" value={metricsForm.impressions} onChange={(e) => setMetricsForm({ ...metricsForm, impressions: e.target.value })} style={inputStyle} /><input placeholder="Clicks" value={metricsForm.clicks} onChange={(e) => setMetricsForm({ ...metricsForm, clicks: e.target.value })} style={inputStyle} /><input placeholder="Likes" value={metricsForm.likes} onChange={(e) => setMetricsForm({ ...metricsForm, likes: e.target.value })} style={inputStyle} /><input placeholder="Comments" value={metricsForm.comments} onChange={(e) => setMetricsForm({ ...metricsForm, comments: e.target.value })} style={inputStyle} /><input placeholder="Shares" value={metricsForm.shares} onChange={(e) => setMetricsForm({ ...metricsForm, shares: e.target.value })} style={inputStyle} /><button onClick={addMetrics} disabled={!selectedContentId}>Save metrics</button></section>
                    <section className="card"><h4>Analytics summary</h4>{analytics ? (<><p>Content items: {analytics.content_count}</p><p>Impressions: {analytics.totals.impressions} · Clicks: {analytics.totals.clicks} · Likes: {analytics.totals.likes} · Comments: {analytics.totals.comments} · Shares: {analytics.totals.shares}</p><ul>{analytics.items.map((item) => (<li key={item.content_item_id}>{item.title} ({item.channel}) — {item.impressions} impressions, {item.clicks} clicks</li>))}</ul></>) : (<p>No analytics yet.</p>)}</section>
                  </div>

                  <section className="card" style={{ marginTop: 16 }}><h4>Publishing queue</h4><p>Queue selected content for approval-based publishing.</p><input placeholder="Schedule for (ISO datetime optional)" value={publishForm.scheduled_for} onChange={(e) => setPublishForm({ scheduled_for: e.target.value })} style={inputStyle} /><button onClick={queuePublish} disabled={!selectedContentId}>Queue publish</button><div style={{ marginTop: 12 }}>{publishQueue.length === 0 ? <p>No publish jobs yet.</p> : null}<div style={{ display: 'grid', gap: 10 }}>{publishQueue.map((job) => (<div key={job.id} className="card" style={{ borderStyle: 'dashed' }}><strong>Job #{job.id}</strong><div>Status: {job.status} · attempts: {job.attempts}</div>{job.scheduled_for ? <div>Scheduled: {job.scheduled_for}</div> : null}{job.published_at ? <div>Published: {job.published_at}</div> : null}{job.last_error ? <div>Error: {job.last_error}</div> : null}<div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}><button onClick={() => updatePublishJob(job.id, 'sent')} style={{ background: '#16a34a' }}>Mark sent</button><button onClick={() => updatePublishJob(job.id, 'failed')} style={{ background: '#dc2626' }}>Mark failed</button><button onClick={() => updatePublishJob(job.id, 'queued')}>Requeue</button></div></div>))}</div></div></section>
                </section>
              ) : null}
            </section>
          ) : null}
        </div>
      )}
    </main>
  );
}

const inputStyle: React.CSSProperties = { width: '100%', marginBottom: 12, padding: '12px 14px', borderRadius: 12, border: '1px solid #d1d5db', fontSize: 15 };
const linkButtonStyle: React.CSSProperties = { border: 'none', background: 'transparent', color: '#2563eb', cursor: 'pointer', font: 'inherit' };
const selectButtonStyle: React.CSSProperties = { width: '100%', borderRadius: 12, padding: '12px 14px', border: '1px solid #d1d5db', textAlign: 'left', cursor: 'pointer', background: '#fff' };
