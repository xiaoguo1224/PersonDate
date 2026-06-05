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
};

export type ApiEnvelope<T> = {
  success: boolean;
  data: T;
  message?: string | null;
};
