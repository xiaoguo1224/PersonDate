export type SystemSettingItem = {
  key: string;
  value?: unknown;
  is_sensitive: boolean;
  description?: string | null;
  is_configured: boolean;
  created_at: string;
  updated_at: string;
};

export type SystemSettingsResponse = {
  items: SystemSettingItem[];
};

export type SystemSettingsFormValues = {
  DEFAULT_TIMEZONE?: string;
  REMINDER_SCAN_INTERVAL_SECONDS?: number;
  DEFAULT_REMIND_BEFORE_MINUTES?: number;
  SYSTEM_DAILY_PUSH_ENABLED?: boolean;
  LLM_BASE_URL?: string;
  LLM_MODEL?: string;
  LLM_API_KEY?: string;
  WEATHER_API_PROVIDER?: string;
  WEATHER_API_KEY?: string;
};

export function getSettingValue(items: SystemSettingItem[], key: string): SystemSettingItem | undefined {
  return items.find((item) => item.key === key);
}
