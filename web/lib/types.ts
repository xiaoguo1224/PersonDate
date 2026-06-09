export type UserRole = "owner" | "member";

export type AuthSession = {
  accessToken: string;
  tokenType: "bearer";
  userId?: string;
  role: UserRole;
  username?: string;
  displayName?: string | null;
  email?: string | null;
};

export type AuthMeResponse = {
  id: string;
  username: string;
  display_name?: string | null;
  email?: string | null;
  role: UserRole;
  status: string;
  default_timezone?: string | null;
};

export type UserSettingsResponse = {
  default_timezone: string;
  workday_start_time?: string | null;
  workday_end_time?: string | null;
  daily_plan_push_time?: string | null;
  default_remind_before_minutes?: number | null;
  daily_plan_push_enabled: boolean;
  city?: string | null;
};

export type AgentLogItem = {
  id: string;
  user_id?: string | null;
  channel: string;
  conversation_id?: string | null;
  input_text: string;
  intent?: string | null;
  graph_trace?: string[] | null;
  tools_called?: Array<Record<string, unknown>> | null;
  tool_results?: Array<Record<string, unknown>> | null;
  final_response?: string | null;
  success: boolean;
  error_message?: string | null;
  created_at: string;
};

export type AgentLogListResponse = {
  items: AgentLogItem[];
};

export type WechatLoginSessionCreateResponse = {
  login_session_id: string;
  qr_payload: string;
  qr_img_content?: string;  // 新增: base64 二维码图片
  expires_at: string;
  status: string;
};

export type WechatLoginSessionItem = {
  id: string;
  owner_user_id: string;
  login_session_id: string;
  qr_payload: string;
  status: string;
  expires_at: string;
  confirmed_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type WechatAccountItem = {
  id: string;
  owner_user_id: string;
  account_id: string;
  wechat_user_id?: string | null;
  base_url: string;
  cursor?: string | null;
  remark?: string | null;
  status: string;
  bind_time?: string | null;
  last_active_time?: string | null;
  created_at: string;
  updated_at: string;
};

export type WechatAccountListResponse = {
  items: WechatAccountItem[];
};

export type ChannelIdentityItem = {
  id: string;
  user_id: string;
  channel: string;
  channel_user_id: string;
  conversation_id: string;
  display_name?: string | null;
  avatar_url?: string | null;
  status: string;
  bound_at?: string | null;
  created_at: string;
};

export type ChannelIdentityListResponse = {
  items: ChannelIdentityItem[];
};

export type ChannelMessageLogItem = {
  id: string;
  user_id?: string | null;
  channel: string;
  account_id?: string | null;
  message_id?: string | null;
  conversation_id: string;
  channel_user_id?: string | null;
  direction: string;
  content_type: string;
  content?: string | null;
  context_token?: string | null;
  raw_payload?: Record<string, unknown> | null;
  status: string;
  retry_count: number;
  error_code?: string | null;
  error_message?: string | null;
  created_at: string;
};

export type ChannelMessageLogListResponse = {
  items: ChannelMessageLogItem[];
};

export type WechatOutboundQueueItem = {
  id: string;
  account_id: string;
  message_id: string;
  to_user_id: string;
  conversation_id: string;
  content: string;
  context_token?: string | null;
  raw_payload?: Record<string, unknown> | null;
  status: string;
  retry_count: number;
  error_code?: string | null;
  error_message?: string | null;
  sent_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type WechatOutboundQueueListResponse = {
  items: WechatOutboundQueueItem[];
};

export type WechatStatusResponse = {
  connected: boolean;
  channel_token_configured: boolean;
  total_accounts: number;
  active_accounts: number;
  queued_outbound_messages: number;
  sent_outbound_messages: number;
  failed_outbound_messages: number;
  total_identities: number;
  active_identities: number;
  bound_users: number;
  last_message_at?: string | null;
  recent_inbound_messages: ChannelMessageLogItem[];
  recent_outbound_messages: ChannelMessageLogItem[];
};

export type ApiEnvelope<T> = {
  success: boolean;
  data: T;
  message?: string | null;
};
