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

export type ApiEnvelope<T> = {
  success: boolean;
  data: T;
  message?: string | null;
};
