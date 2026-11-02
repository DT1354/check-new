export type Account = {
  id: number
  alias: string
  username_hint: string
  enabled: boolean
  created_at: string
  updated_at: string
}

export type Run = {
  id: number
  account_id: number
  account_alias: string | null
  trigger: string
  status: string
  attempt_count: number
  message: string | null
  checkin_time: string | null
  started_at: string | null
  finished_at: string | null
  created_at: string
}

export type Invite = {
  id: number
  expires_at: string
  used_at: string | null
  revoked_at: string | null
  created_at: string
  invite_url?: string
}

export type NotificationSettings = {
  webhook_configured: boolean
  signing_secret_configured: boolean
  notify_manual_runs: boolean
}
