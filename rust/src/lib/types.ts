export interface ServiceEvent {
  id: number;
  type: EventType;
  source: string;
  timestamp: string;
  payload: Record<string, unknown>;
}

export type EventType = "status" | "message" | "log" | "error" | "task_state";

export interface TaskState {
  monitoring: boolean;
  sidebar: boolean;
}

export interface TranslatorServiceStatus {
  enabled: boolean;
  configured: boolean;
  checking: boolean;
  healthy: boolean | null;
  last_error: string | null;
  provider: string;
}

export interface ListenSettings {
  mode: string;
  targets: string[];
  interval_seconds: number;
  dedupe_window_seconds: number;
  session_preview_dedupe_window_seconds: number;
  cross_source_merge_window_seconds: number;
  focus_refresh: boolean;
  worker_debug: boolean;
  use_right_panel_details: boolean;
}

export interface TranslateSettings {
  enabled: boolean;
  provider: string;
  deeplx_url: string;
  source_lang: string;
  target_lang: string;
  timeout_seconds: number;
  max_concurrency: number;
  max_requests_per_second: number;
  // AI 翻译相关字段
  ai_provider_id: string;
  ai_model_id: string;
  ai_api_key: string;
  ai_base_url: string;
}


export interface SidebarAppearance {
  bg_opacity: number;
  blur: "none" | "weak" | "medium" | "strong";
  card_style: "transparent" | "light" | "standard" | "dark";
  text_enhance: "none" | "shadow" | "bold";
}

export interface DisplaySettings {
  english_only: boolean;
  on_translate_fail: string;
  width: number;
  side: string;
  collapsed_display_count: number;
  ghost_mode: boolean;
  sidebar_appearance: SidebarAppearance;
}

export interface LoggingSettings {
  file: string;
}

export interface DictSettings {
  provider: string;
}

export interface AppSettings {
  listen: ListenSettings;
  translate: TranslateSettings;
  display: DisplaySettings;
  logging: LoggingSettings;
  dict: DictSettings;
}

export interface AppRuntime {
  tasks: TaskState;
  translator: TranslatorServiceStatus;
  close_to_tray: boolean;
}

export interface AppStateSnapshot {
  settings: AppSettings;
  runtime: AppRuntime;
}

export interface ServiceStatus {
  adapter: {
    platform: string;
    supported: boolean;
    reason: string;
  };
  tasks: TaskState;
  translator: TranslatorServiceStatus;
}

export interface ApiResponse<T = unknown> {
  ok: boolean;
  message?: string;
  data?: T;
}

export interface SidebarMessage {
  id: number;
  chatName: string;
  chatType?: string;
  sender: string;
  textCn: string;
  textEn: string;
  translateError: string;
  timestamp: string;
  isSelf: boolean;
  imagePath?: string;
}

export interface StoredMessage {
  id: number;
  chat_name: string;
  chat_type?: string;
  sender: string;
  content: string;
  content_en: string;
  is_self: boolean;
  detected_at: string;
  image_path?: string;
  source?: string;
  quality?: string;
}

export interface SidebarSnapshot {
  current_chat?: string | null;
  messages: StoredMessage[];
  translator: TranslatorServiceStatus;
  refresh_version?: number;
}
