import {
  Bell,
  Check,
  ChevronRight,
  CircleAlert,
  Clock3,
  Copy,
  KeyRound,
  Link2,
  LoaderCircle,
  LogOut,
  Play,
  Plus,
  RefreshCw,
  RotateCcw,
  Settings2,
  ShieldCheck,
  Sparkles,
  Trash2,
  UserRound,
  UsersRound,
  X,
} from 'lucide-react'
import { FormEvent, ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from './api'
import type { Account, Invite, NotificationSettings, Run } from './types'

type Tab = 'tonight' | 'accounts' | 'runs' | 'settings'
type Toast = { kind: 'success' | 'error'; text: string }

const statusMeta: Record<string, { label: string; tone: string }> = {
  queued: { label: '等待执行', tone: 'neutral' },
  running: { label: '执行中', tone: 'working' },
  success: { label: '打卡成功', tone: 'success' },
  already_checked: { label: '今日已打卡', tone: 'success' },
  failed: { label: '执行失败', tone: 'danger' },
  out_of_time: { label: '非打卡时段', tone: 'warning' },
}

function formatTime(value: string | null | undefined, includeDate = false) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    month: includeDate ? '2-digit' : undefined,
    day: includeDate ? '2-digit' : undefined,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value))
}

function AppMark() {
  return (
    <div className="app-mark" aria-hidden="true">
      <span className="mark-orbit" />
      <span className="mark-dot" />
    </div>
  )
}

function Button({
  children,
  variant = 'secondary',
  busy = false,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  busy?: boolean
}) {
  return (
    <button className={`button button-${variant}`} disabled={busy || props.disabled} {...props}>
      {busy ? <LoaderCircle size={15} className="spin" /> : null}
      {children}
    </button>
  )
}

function Status({ status }: { status?: string }) {
  if (!status) return <span className="status neutral"><span />暂无记录</span>
  const meta = statusMeta[status] || { label: status, tone: 'neutral' }
  return <span className={`status ${meta.tone}`}><span />{meta.label}</span>
}

function ToastView({ toast, dismiss }: { toast: Toast; dismiss: () => void }) {
  return (
    <div className={`toast toast-${toast.kind}`} role="status">
      {toast.kind === 'success' ? <Check size={16} /> : <CircleAlert size={16} />}
      <span>{toast.text}</span>
      <button onClick={dismiss} aria-label="关闭提示"><X size={14} /></button>
    </div>
  )
}

function Login({ onLogin }: { onLogin: (username: string) => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const session = await api.login(username.trim(), password)
      onLogin(session.username)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '登录失败')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-card">
        <div className="auth-heading">
          <AppMark />
          <div>
            <p className="eyebrow">CHECK-IN CONSOLE</p>
            <h1>晚上好</h1>
            <p>登录后管理今晚的自动打卡。</p>
          </div>
        </div>
        <form onSubmit={submit} className="form-stack">
          <label>管理员账号<input autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} required /></label>
          <label>密码<input type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} minLength={8} required /></label>
          {error ? <p className="form-error"><CircleAlert size={14} />{error}</p> : null}
          <Button type="submit" variant="primary" busy={busy}>进入控制台<ChevronRight size={15} /></Button>
        </form>
        <p className="auth-foot"><ShieldCheck size={14} />凭据仅发送到你的私有服务器</p>
      </section>
    </main>
  )
}

function InviteEnrollment({ token }: { token: string }) {
  const [status, setStatus] = useState<'loading' | 'ready' | 'done' | 'invalid'>('loading')
  const [alias, setAlias] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.get(`/api/invites/${encodeURIComponent(token)}/status`)
      .then(() => setStatus('ready'))
      .catch(() => setStatus('invalid'))
  }, [token])

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await api.publicPost(`/api/invites/${encodeURIComponent(token)}/enroll`, {
        alias: alias.trim(), username: username.trim(), password,
      })
      setStatus('done')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '保存失败')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="auth-shell invite-shell">
      <section className="auth-card invite-card">
        <div className="auth-heading"><AppMark /><div><p className="eyebrow">PRIVATE INVITATION</p><h1>加入自动打卡</h1><p>填写一次即可，之后无需每天操作。</p></div></div>
        {status === 'loading' ? <div className="empty-state"><LoaderCircle className="spin" /><p>正在确认邀请…</p></div> : null}
        {status === 'invalid' ? <div className="result-state"><CircleAlert /><h2>邀请已失效</h2><p>链接可能已被使用、撤销或超过 24 小时。</p></div> : null}
        {status === 'done' ? <div className="result-state success-result"><Check /><h2>已经保存</h2><p>你的账号已加入，今晚会由管理员统一查看结果。</p></div> : null}
        {status === 'ready' ? (
          <form onSubmit={submit} className="form-stack">
            <label>怎么称呼你<input value={alias} onChange={e => setAlias(e.target.value)} placeholder="例如：小林" required /></label>
            <label>办事大厅账号<input autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} required /></label>
            <label>办事大厅密码<input type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required /></label>
            <p className="field-note"><KeyRound size={13} />账号与密码会加密存储在管理员的服务器中。</p>
            {error ? <p className="form-error"><CircleAlert size={14} />{error}</p> : null}
            <Button type="submit" variant="primary" busy={busy}>保存并加入<ChevronRight size={15} /></Button>
          </form>
        ) : null}
      </section>
    </main>
  )
}

function PageHeader({ eyebrow, title, description, actions }: { eyebrow: string; title: string; description: string; actions?: ReactNode }) {
  return <div className="page-header"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p>{description}</p></div>{actions ? <div className="header-actions">{actions}</div> : null}</div>
}

function Tonight({ accounts, runs, busyAction, action }: {
  accounts: Account[]
  runs: Run[]
  busyAction: string
  action: (key: string, path: string) => Promise<void>
}) {
  const latest = useMemo(() => {
    const map = new Map<number, Run>()
    runs.forEach(run => { if (!map.has(run.account_id)) map.set(run.account_id, run) })
    return map
  }, [runs])
  const succeeded = accounts.filter(account => ['success', 'already_checked'].includes(latest.get(account.id)?.status || '')).length
  const failed = accounts.filter(account => ['failed', 'out_of_time'].includes(latest.get(account.id)?.status || '')).length

  return (
    <>
      <PageHeader eyebrow="TONIGHT · 21:05" title="今晚的打卡" description="自动任务每天运行一次；失败账号会在 10 秒后自动重试一次。" actions={<><Button onClick={() => action('failed', '/api/runs/failed')} busy={busyAction === 'failed'}><RotateCcw size={15} />重试失败</Button><Button variant="primary" onClick={() => action('all', '/api/runs/all')} busy={busyAction === 'all'}><Play size={15} />全部检查并打卡</Button></>} />
      <section className="summary-strip">
        <div><span>已启用</span><strong>{accounts.filter(a => a.enabled).length}</strong></div>
        <div><span>今日成功</span><strong className="success-text">{succeeded}</strong></div>
        <div><span>需要留意</span><strong className={failed ? 'danger-text' : ''}>{failed}</strong></div>
        <div className="summary-note"><Sparkles size={16} /><p>只有最终结果会显示在这里，不展示浏览器内部步骤。</p></div>
      </section>
      <section className="panel list-panel">
        <div className="panel-title"><div><h2>账号状态</h2><p>{accounts.length ? `共 ${accounts.length} 个账号` : '还没有添加账号'}</p></div></div>
        {accounts.length === 0 ? <Empty icon={<UsersRound />} title="还没有账号" text="在“账号”页面添加，或生成邀请链接。" /> : (
          <div className="account-list">
            {accounts.map(account => {
              const run = latest.get(account.id)
              return <div className={`account-row ${!account.enabled ? 'is-disabled' : ''}`} key={account.id}>
                <div className="avatar">{account.alias.slice(0, 1).toUpperCase()}</div>
                <div className="account-primary"><strong>{account.alias}</strong><span>{account.username_hint}{!account.enabled ? ' · 已停用' : ''}</span></div>
                <div className="row-status"><Status status={run?.status} /><small>{run ? (run.checkin_time || formatTime(run.finished_at)) : '等待首次执行'}</small></div>
                <div className="row-message">{run?.message || '尚无运行记录'}</div>
                <Button variant="ghost" disabled={!account.enabled || run?.status === 'queued' || run?.status === 'running'} busy={busyAction === `account-${account.id}`} onClick={() => action(`account-${account.id}`, `/api/runs/account/${account.id}`)}><Play size={15} />手动打卡</Button>
              </div>
            })}
          </div>
        )}
      </section>
    </>
  )
}

function Empty({ icon, title, text }: { icon: ReactNode; title: string; text: string }) {
  return <div className="empty-state">{icon}<h3>{title}</h3><p>{text}</p></div>
}

type AccountDraft = { alias: string; username: string; password: string; enabled: boolean }
const blankAccount: AccountDraft = { alias: '', username: '', password: '', enabled: true }

function AccountModal({ account, close, saved }: { account: Account | null; close: () => void; saved: () => Promise<void> }) {
  const [draft, setDraft] = useState<AccountDraft>(account ? { alias: account.alias, username: '', password: '', enabled: account.enabled } : blankAccount)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      if (account) {
        const payload: Record<string, string | boolean> = { alias: draft.alias.trim(), enabled: draft.enabled }
        if (draft.username.trim()) payload.username = draft.username.trim()
        if (draft.password) payload.password = draft.password
        await api.patch(`/api/accounts/${account.id}`, payload)
      } else {
        await api.post('/api/accounts', { ...draft, alias: draft.alias.trim(), username: draft.username.trim() })
      }
      await saved()
      close()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '保存失败')
    } finally { setBusy(false) }
  }

  return <div className="modal-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) close() }}><section className="modal" role="dialog" aria-modal="true"><div className="modal-head"><div><p className="eyebrow">{account ? 'EDIT ACCOUNT' : 'NEW ACCOUNT'}</p><h2>{account ? '编辑账号' : '添加账号'}</h2></div><button onClick={close} aria-label="关闭"><X /></button></div><form onSubmit={submit} className="form-stack"><label>昵称<input value={draft.alias} onChange={e => setDraft({ ...draft, alias: e.target.value })} required /></label><label>办事大厅账号<input autoComplete="off" value={draft.username} onChange={e => setDraft({ ...draft, username: e.target.value })} placeholder={account ? '留空表示不修改' : ''} required={!account} /></label><label>办事大厅密码<input type="password" autoComplete="new-password" value={draft.password} onChange={e => setDraft({ ...draft, password: e.target.value })} placeholder={account ? '留空表示不修改' : ''} required={!account} /></label><label className="switch-row"><span><strong>启用自动打卡</strong><small>停用后不会加入自动或批量任务</small></span><input type="checkbox" checked={draft.enabled} onChange={e => setDraft({ ...draft, enabled: e.target.checked })} /></label>{error ? <p className="form-error"><CircleAlert size={14} />{error}</p> : null}<div className="modal-actions"><Button type="button" onClick={close}>取消</Button><Button type="submit" variant="primary" busy={busy}>保存</Button></div></form></section></div>
}

function AccountsPage({ accounts, invites, reload, notify }: { accounts: Account[]; invites: Invite[]; reload: () => Promise<void>; notify: (toast: Toast) => void }) {
  const [editing, setEditing] = useState<Account | null | undefined>(undefined)
  const [inviteBusy, setInviteBusy] = useState(false)
  const [newInvite, setNewInvite] = useState('')

  async function createInvite() {
    setInviteBusy(true)
    try {
      const created = await api.post<Invite>('/api/invites', { expires_in_hours: 24 })
      setNewInvite(created.invite_url || '')
      await reload()
    } catch (reason) { notify({ kind: 'error', text: reason instanceof Error ? reason.message : '创建邀请失败' }) }
    finally { setInviteBusy(false) }
  }

  async function copyInvite() {
    await navigator.clipboard.writeText(newInvite)
    notify({ kind: 'success', text: '邀请链接已复制' })
  }

  async function remove(account: Account) {
    if (!window.confirm(`确定删除“${account.alias}”及其历史记录吗？`)) return
    try { await api.delete(`/api/accounts/${account.id}`); await reload(); notify({ kind: 'success', text: '账号已删除' }) }
    catch (reason) { notify({ kind: 'error', text: reason instanceof Error ? reason.message : '删除失败' }) }
  }

  return <><PageHeader eyebrow="ACCOUNTS & INVITES" title="账号与邀请" description="凭据由服务器主密钥加密；页面只显示账号末四位。" actions={<><Button onClick={createInvite} busy={inviteBusy}><Link2 size={15} />生成邀请</Button><Button variant="primary" onClick={() => setEditing(null)}><Plus size={15} />添加账号</Button></>} />
    {newInvite ? <section className="invite-banner"><div><Link2 size={18} /><div><strong>24 小时一次性邀请已生成</strong><p>{newInvite}</p></div></div><Button onClick={copyInvite}><Copy size={15} />复制链接</Button></section> : null}
    <section className="panel"><div className="panel-title"><div><h2>已保存账号</h2><p>{accounts.length} 个账号，其中 {accounts.filter(a => a.enabled).length} 个已启用</p></div></div>{accounts.length === 0 ? <Empty icon={<UserRound />} title="从第一个账号开始" text="可以由你添加，也可以把一次性链接发给对方填写。" /> : <div className="management-list">{accounts.map(account => <div className="management-row" key={account.id}><div className="avatar">{account.alias.slice(0, 1)}</div><div className="account-primary"><strong>{account.alias}</strong><span>{account.username_hint}</span></div><span className={`status ${account.enabled ? 'success' : 'neutral'}`}><span />{account.enabled ? '已启用' : '已停用'}</span><span className="enabled-label">{account.enabled ? '自动任务' : '不会执行'}</span><button className="icon-button" onClick={() => setEditing(account)} aria-label={`编辑 ${account.alias}`}><Settings2 size={17} /></button><button className="icon-button danger-icon" onClick={() => remove(account)} aria-label={`删除 ${account.alias}`}><Trash2 size={17} /></button></div>)}</div>}</section>
    <section className="panel compact-panel"><div className="panel-title"><div><h2>最近邀请</h2><p>链接默认 24 小时有效且只能使用一次</p></div></div><div className="invite-list">{invites.slice(0, 6).map(invite => <div key={invite.id}><span>邀请 #{invite.id}</span><small>{invite.used_at ? '已使用' : invite.revoked_at ? '已撤销' : new Date(invite.expires_at) < new Date() ? '已过期' : '等待填写'}</small><time>{formatTime(invite.created_at, true)}</time></div>)}{invites.length === 0 ? <p className="muted-line">还没有生成过邀请。</p> : null}</div></section>
    {editing !== undefined ? <AccountModal account={editing} close={() => setEditing(undefined)} saved={reload} /> : null}</>
}

function RunsPage({ runs }: { runs: Run[] }) {
  return <><PageHeader eyebrow="RUN HISTORY" title="运行记录" description="保留最终状态、执行时间与安全处理后的错误信息。" /><section className="panel table-panel">{runs.length === 0 ? <Empty icon={<Clock3 />} title="还没有运行记录" text="自动或手动执行后，结果会出现在这里。" /> : <div className="run-table"><div className="run-head"><span>账号</span><span>来源</span><span>状态</span><span>尝试</span><span>完成时间</span><span>说明</span></div>{runs.map(run => <div className="run-line" key={run.id}><strong>{run.account_alias || `账号 #${run.account_id}`}</strong><span>{run.trigger === 'automatic' ? '自动' : run.trigger === 'manual_bulk' ? '批量手动' : run.trigger === 'manual_retry' ? '失败重试' : '单人手动'}</span><Status status={run.status} /><span>{run.attempt_count || '—'}</span><span>{formatTime(run.finished_at || run.created_at, true)}</span><span className="run-message" title={run.message || ''}>{run.message || '—'}</span></div>)}</div>}</section></>
}

function SettingsPage({ initial, reload, notify }: { initial: NotificationSettings | null; reload: () => Promise<void>; notify: (toast: Toast) => void }) {
  const [webhook, setWebhook] = useState('')
  const [secret, setSecret] = useState('')
  const [manual, setManual] = useState(initial?.notify_manual_runs || false)
  const [busy, setBusy] = useState('')
  useEffect(() => setManual(initial?.notify_manual_runs || false), [initial])

  async function save(event: FormEvent) {
    event.preventDefault(); setBusy('save')
    try {
      await api.put('/api/settings/notifications', {
        webhook_url: webhook || undefined,
        signing_secret: secret || undefined,
        notify_manual_runs: manual,
      })
      setWebhook(''); setSecret(''); await reload(); notify({ kind: 'success', text: '通知设置已保存' })
    } catch (reason) { notify({ kind: 'error', text: reason instanceof Error ? reason.message : '保存失败' }) }
    finally { setBusy('') }
  }

  async function test() {
    setBusy('test')
    try { await api.post('/api/settings/notifications/test'); notify({ kind: 'success', text: '测试消息已发送' }) }
    catch (reason) { notify({ kind: 'error', text: reason instanceof Error ? reason.message : '发送失败' }) }
    finally { setBusy('') }
  }

  return <><PageHeader eyebrow="NOTIFICATIONS" title="通知设置" description="每天自动批次结束后，把一条简洁汇总发送到飞书。" /><section className="settings-grid"><form className="panel settings-form" onSubmit={save}><div className="panel-title"><div><h2>飞书机器人</h2><p>Webhook 与签名密钥只保存在加密数据库中</p></div><Bell size={19} /></div><div className="form-stack"><label>Webhook 地址<input type="url" value={webhook} onChange={e => setWebhook(e.target.value)} placeholder={initial?.webhook_configured ? '已配置；留空表示不修改' : 'https://open.feishu.cn/open-apis/bot/v2/hook/…'} /></label><label>签名密钥<input type="password" value={secret} onChange={e => setSecret(e.target.value)} placeholder={initial?.signing_secret_configured ? '已配置；留空表示不修改' : '可选，建议在飞书开启签名校验'} /></label><label className="switch-row"><span><strong>手动任务也发送通知</strong><small>自动任务始终在整个批次结束后汇总</small></span><input type="checkbox" checked={manual} onChange={e => setManual(e.target.checked)} /></label><div className="settings-actions"><Button type="button" onClick={test} busy={busy === 'test'} disabled={!initial?.webhook_configured}>发送测试</Button><Button type="submit" variant="primary" busy={busy === 'save'}>保存设置</Button></div></div></form><aside className="panel guide-panel"><div className="guide-icon"><ShieldCheck /></div><h2>一条消息，看清全局</h2><p>自动批次完成后仅发送总数、成功与失败数量，不发送账号、密码或学校接口响应原文。</p><ol><li><span>1</span>在飞书群添加自定义机器人</li><li><span>2</span>复制 Webhook，建议开启签名校验</li><li><span>3</span>保存后发送一次测试消息</li></ol></aside></section></>
}

export default function App() {
  const inviteMatch = window.location.pathname.match(/^\/invite\/([^/]+)$/)
  const [auth, setAuth] = useState<'loading' | 'guest' | 'ready'>('loading')
  const [username, setUsername] = useState('')
  const [tab, setTab] = useState<Tab>('tonight')
  const [accounts, setAccounts] = useState<Account[]>([])
  const [runs, setRuns] = useState<Run[]>([])
  const [invites, setInvites] = useState<Invite[]>([])
  const [settings, setSettings] = useState<NotificationSettings | null>(null)
  const [loading, setLoading] = useState(false)
  const [busyAction, setBusyAction] = useState('')
  const [toast, setToast] = useState<Toast | null>(null)
  const delayedRefresh = useRef<number | null>(null)

  const loadAll = useCallback(async () => {
    setLoading(true)
    try {
      const [nextAccounts, nextRuns, nextInvites, nextSettings] = await Promise.all([
        api.get<Account[]>('/api/accounts'), api.get<Run[]>('/api/runs?limit=200'),
        api.get<Invite[]>('/api/invites'), api.get<NotificationSettings>('/api/settings/notifications'),
      ])
      setAccounts(nextAccounts); setRuns(nextRuns); setInvites(nextInvites); setSettings(nextSettings)
    } catch (reason) {
      const status = (reason as Error & { status?: number }).status
      if (status === 401) setAuth('guest')
      else setToast({ kind: 'error', text: reason instanceof Error ? reason.message : '刷新失败' })
    } finally { setLoading(false) }
  }, [])

  useEffect(() => {
    if (inviteMatch) return
    api.session().then(session => { setUsername(session.username); setAuth('ready') }).catch(() => setAuth('guest'))
  }, [])

  useEffect(() => { if (auth === 'ready') void loadAll() }, [auth, loadAll])
  useEffect(() => {
    function onFocus() { if (auth === 'ready') void loadAll() }
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [auth, loadAll])
  useEffect(() => () => { if (delayedRefresh.current) window.clearTimeout(delayedRefresh.current) }, [])
  useEffect(() => { if (!toast) return; const timer = window.setTimeout(() => setToast(null), 4200); return () => window.clearTimeout(timer) }, [toast])

  if (inviteMatch) return <InviteEnrollment token={decodeURIComponent(inviteMatch[1])} />
  if (auth === 'loading') return <main className="splash"><AppMark /><LoaderCircle className="spin" /></main>
  if (auth === 'guest') return <Login onLogin={name => { setUsername(name); setAuth('ready') }} />

  async function execute(key: string, path: string) {
    setBusyAction(key)
    try {
      const created = await api.post<Run[]>(path)
      setToast({ kind: 'success', text: created.length ? `已加入 ${created.length} 个任务` : '没有需要加入的任务' })
      await loadAll()
      if (delayedRefresh.current) window.clearTimeout(delayedRefresh.current)
      delayedRefresh.current = window.setTimeout(() => void loadAll(), 60_000)
    } catch (reason) { setToast({ kind: 'error', text: reason instanceof Error ? reason.message : '操作失败' }) }
    finally { setBusyAction('') }
  }

  async function logout() {
    try { await api.logout() } finally { setAuth('guest'); setAccounts([]); setRuns([]) }
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: 'tonight', label: '今晚' }, { id: 'accounts', label: '账号' },
    { id: 'runs', label: '记录' }, { id: 'settings', label: '设置' },
  ]

  return <div className="app-shell">
    <header className="topbar"><div className="brand"><AppMark /><div><strong>Check-in</strong><span>SWU · Freshman</span></div></div><nav>{tabs.map(item => <button key={item.id} className={tab === item.id ? 'active' : ''} onClick={() => setTab(item.id)}>{item.label}</button>)}</nav><div className="top-actions"><button className="icon-button" onClick={() => void loadAll()} aria-label="刷新" title="刷新"><RefreshCw size={17} className={loading ? 'spin' : ''} /></button><div className="user-chip"><span>{username.slice(0, 1).toUpperCase()}</span><p>{username}</p></div><button className="icon-button" onClick={logout} aria-label="退出登录" title="退出登录"><LogOut size={17} /></button></div></header>
    <main className="content">
      {tab === 'tonight' ? <Tonight accounts={accounts} runs={runs} busyAction={busyAction} action={execute} /> : null}
      {tab === 'accounts' ? <AccountsPage accounts={accounts} invites={invites} reload={loadAll} notify={setToast} /> : null}
      {tab === 'runs' ? <RunsPage runs={runs} /> : null}
      {tab === 'settings' ? <SettingsPage initial={settings} reload={loadAll} notify={setToast} /> : null}
    </main>
    {toast ? <ToastView toast={toast} dismiss={() => setToast(null)} /> : null}
  </div>
}
