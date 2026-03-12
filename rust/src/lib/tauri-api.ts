import { invoke, convertFileSrc } from "@tauri-apps/api/core";
import type { ApiResponse, AppSettings, AppStateSnapshot, SidebarSnapshot } from "./types";

export async function appStateGet(): Promise<ApiResponse<AppStateSnapshot>> {
  return invoke("app_state_get");
}

export interface SettingsUpdateResponse extends ApiResponse<AppStateSnapshot> {
  errors?: string[];
  path?: string;
}

export async function settingsUpdate(settings: AppSettings): Promise<SettingsUpdateResponse> {
  return invoke("settings_update", { settings });
}

export async function getSessions(): Promise<ApiResponse<string[]>> {
  return invoke("get_sessions");
}

export async function listenStart(intervalSeconds?: number): Promise<ApiResponse> {
  return invoke("listen_start", { intervalSeconds });
}

export async function listenStop(): Promise<ApiResponse> {
  return invoke("listen_stop");
}

export async function sidebarStart(params: {
  targets?: string[];
  translateEnabled?: boolean;
  deeplxUrl?: string;
  sourceLang?: string;
  targetLang?: string;
  timeoutSeconds?: number;
  maxConcurrency?: number;
  maxRequestsPerSecond?: number;
  imageCapture?: boolean;
}): Promise<ApiResponse> {
  return invoke("sidebar_start", params);
}

export async function sidebarStop(): Promise<ApiResponse> {
  return invoke("sidebar_stop");
}

export async function liveStart(params?: {
  translateEnabled?: boolean;
  provider?: string;
  deeplxUrl?: string;
  aiProviderId?: string;
  aiModelId?: string;
  aiApiKey?: string;
  aiBaseUrl?: string;
  sourceLang?: string;
  targetLang?: string;
  intervalSeconds?: number;
  timeoutSeconds?: number;
  maxConcurrency?: number;
  maxRequestsPerSecond?: number;
  imageCapture?: boolean;
  windowMode?: string;
}): Promise<ApiResponse> {
  return invoke("live_start", params ?? {});
}

export async function sidebarWindowOpen(width?: number, windowMode?: string): Promise<ApiResponse> {
  return invoke("sidebar_window_open", { width, windowMode });
}

export async function sidebarWindowClose(): Promise<ApiResponse> {
  return invoke("sidebar_window_close");
}

export async function sidebarSnapshotGet(params?: {
  chatName?: string;
  limit?: number;
}): Promise<ApiResponse<SidebarSnapshot>> {
  return invoke("sidebar_snapshot_get", params ?? {});
}

export async function getTaskStatus(): Promise<ApiResponse> {
  return invoke("get_task_status");
}

export async function healthCheck(): Promise<ApiResponse> {
  return invoke("health_check");
}

export async function configGet(): Promise<ApiResponse> {
  return invoke("config_get");
}

export interface ConfigPutResponse {
  ok: boolean;
  errors?: string[];
  message?: string;
  path?: string;
}

export async function configPut(config: unknown): Promise<ConfigPutResponse> {
  return invoke("config_put", { config });
}

export async function configDefault(): Promise<ApiResponse> {
  return invoke("config_default");
}

export async function dbClearRestart(): Promise<ApiResponse> {
  return invoke("db_clear_restart");
}

export async function dbQueryMessages(params: {
  chatName?: string;
  sender?: string;
  keyword?: string;
  limit?: number;
  offset?: number;
}): Promise<ApiResponse> {
  return invoke("db_query_messages", params);
}

export async function dbGetChats(): Promise<ApiResponse> {
  return invoke("db_get_chats");
}

export async function dbGetStats(): Promise<ApiResponse> {
  return invoke("db_get_stats");
}

export async function getCloseToTray(): Promise<boolean> {
  return invoke("get_close_to_tray");
}

export async function setCloseToTray(enabled: boolean): Promise<void> {
  return invoke("set_close_to_tray", { enabled });
}

export interface PreflightResult {
  wechat_running: boolean;
  accessibility_ok: boolean;
  wechat_accessible?: boolean;
  wechat_has_window: boolean;
  can_prompt_accessibility?: boolean;
}

export async function preflightCheck(): Promise<PreflightResult> {
  return invoke("preflight_check");
}

export interface AccessibilityRequestResult {
  trusted_before: boolean;
  prompt_attempted: boolean;
  trusted_after_check: boolean;
  settings_opened: boolean;
}

export interface AccessibilityOpenSettingsResult {
  ok: boolean;
  settings_opened: boolean;
  message?: string;
}

export async function accessibilityRequestAccess(): Promise<AccessibilityRequestResult> {
  return invoke("accessibility_request_access");
}

export async function accessibilityOpenSettings(): Promise<AccessibilityOpenSettingsResult> {
  return invoke("accessibility_open_settings");
}

export async function translateTest(params: {
  provider?: string;
  deeplxUrl?: string;
  aiProviderId?: string;
  aiModelId?: string;
  aiApiKey?: string;
  aiBaseUrl?: string;
  sourceLang?: string;
  targetLang?: string;
  timeoutSeconds?: number;
}): Promise<ApiResponse> {
  return invoke("translate_test", {
    provider: params.provider,
    deeplxUrl: params.deeplxUrl,
    aiProviderId: params.aiProviderId,
    aiModelId: params.aiModelId,
    aiApiKey: params.aiApiKey,
    aiBaseUrl: params.aiBaseUrl,
    sourceLang: params.sourceLang,
    targetLang: params.targetLang,
    timeoutSeconds: params.timeoutSeconds,
  });
}

// ==================== Dictionary API ====================

export interface Phonetic {
  text?: string;
  audio_url?: string;
  region?: string;
}

export interface Definition {
  english: string;
  chinese?: string;
  example?: string;
  example_chinese?: string;
}

export interface Meaning {
  part_of_speech: string;
  part_of_speech_zh: string;
  definitions: Definition[];
  synonyms: string[];
  antonyms: string[];
}

export interface WordEntry {
  word: string;
  summary_zh?: string;
  phonetics: Phonetic[];
  meanings: Meaning[];
  fetched_at: string;
  translation_completed: boolean;
  data_source: string;
}

export interface DictProviderInfo {
  id: string;
  display_name: string;
  requires_network: boolean;
  is_default: boolean;
}

export async function wordLookup(word: string, provider?: string): Promise<WordEntry> {
  return invoke("word_lookup", { word, provider });
}

export async function listDictProviders(): Promise<DictProviderInfo[]> {
  return invoke("list_dict_providers");
}

export async function getDictProvider(): Promise<string> {
  return invoke("get_dict_provider");
}

export async function translateCached(params: {
  text: string;
  sourceLang?: string;
  targetLang?: string;
}): Promise<string> {
  return invoke("translate_cached", params);
}

export async function translateBatch(params: {
  texts: string[];
  sourceLang?: string;
  targetLang?: string;
}): Promise<(string | null)[]> {
  return invoke("translate_batch", params);
}

export async function translateSidebarMessage(params: {
  messageId: number;
  chatName: string;
  sender: string;
  content: string;
  detectedAt: string;
}): Promise<void> {
  return invoke("translate_sidebar_message", {
    messageId: params.messageId,
    chatName: params.chatName,
    sender: params.sender,
    content: params.content,
    detectedAt: params.detectedAt,
  });
}

// ==================== Favorite API ====================

export interface FavoriteWord {
  word: string;
  phonetic?: string;
  meanings_json?: string;
  summary_zh?: string;
  note?: string;
  review_count: number;
  last_review_at?: string;
  created_at: string;
  mastery_level: number;
  next_review_at?: string;
  last_feedback?: number;
  consecutive_correct: number;
}

export interface ReviewSession {
  id: number;
  started_at: string;
  finished_at?: string;
  mode: string;
  total_words: number;
  completed_words: number;
  correct_count: number;
  wrong_count: number;
  fuzzy_count: number;
}

export interface ReviewStats {
  total_favorites: number;
  mastered_count: number;
  reviewing_count: number;
  pending_count: number;
  today_reviewed: number;
  total_reviews: number;
}

export async function toggleFavorite(
  word: string,
  entry?: WordEntry
): Promise<boolean> {
  return invoke("toggle_favorite", { word, entry });
}

export async function isWordFavorited(word: string): Promise<boolean> {
  return invoke("is_word_favorited", { word });
}

export async function getFavoritesBatch(
  words: string[]
): Promise<Record<string, boolean>> {
  return invoke("get_favorites_batch", { words });
}

export async function listFavorites(params?: {
  offset?: number;
  limit?: number;
}): Promise<FavoriteWord[]> {
  return invoke("list_favorites", params ?? {});
}

export async function updateFavoriteNote(
  word: string,
  note: string
): Promise<boolean> {
  return invoke("update_favorite_note", { word, note });
}

export async function recordReview(word: string): Promise<boolean> {
  return invoke("record_review", { word });
}

export async function countFavorites(): Promise<number> {
  return invoke("count_favorites", {});
}

// ==================== Review API ====================

export async function getWordsForReview(limit?: number): Promise<FavoriteWord[]> {
  return invoke("get_words_for_review", { limit });
}

export async function startReviewSession(
  mode: string,
  wordCount: number
): Promise<number> {
  return invoke("start_review_session", { mode, wordCount });
}

export async function recordReviewFeedback(params: {
  sessionId: number;
  word: string;
  feedback: number;
  responseTimeMs?: number;
}): Promise<FavoriteWord> {
  return invoke("record_review_feedback", params);
}

export async function finishReviewSession(
  sessionId: number
): Promise<ReviewSession> {
  return invoke("finish_review_session", { sessionId });
}

export async function getReviewStats(): Promise<ReviewStats> {
  return invoke("get_review_stats", {});
}

// ==================== Audio Cache API ====================

/** 音频缓存统计信息 */
export interface AudioCacheStats {
  /** 缓存文件数量 */
  file_count: number;
  /** 总大小（字节） */
  total_size_bytes: number;
  /** 总大小（MB） */
  total_size_mb: number;
  /** 缓存目录路径 */
  cache_dir: string;
}

/**
 * 将本地文件路径转换为 Tauri asset:// 协议 URL
 * 
 * @param localPath 本地文件绝对路径
 * @returns asset:// 协议 URL，可用于 HTML Audio/Image 等元素
 */
export function localPathToAssetUrl(localPath: string): string {
  // 使用 Tauri 官方的 convertFileSrc 函数
  const url = convertFileSrc(localPath);
  console.log("[localPathToAssetUrl] 原始路径:", localPath);
  console.log("[localPathToAssetUrl] 转换后 URL:", url);
  return url;
}

/**
 * 获取音频播放 URL（自动缓存）
 * 
 * 如果音频已缓存，返回本地文件路径；否则下载并缓存后返回。
 * @param url 远程音频 URL
 * @returns 可用于 HTML Audio 元素的本地 URL
 */
export async function audioGetUrl(url: string): Promise<string> {
  return invoke("audio_get_url", { url });
}

/**
 * 获取音频的 asset:// URL（自动缓存 + 路径转换）
 * 
 * 封装了 audioGetUrl + localPathToAssetUrl 的完整流程
 * @param url 远程音频 URL
 * @returns asset:// 协议 URL，可直接用于 HTML Audio 元素
 */
export async function audioGetAssetUrl(url: string): Promise<string> {
  const localPath = await audioGetUrl(url);
  return localPathToAssetUrl(localPath);
}

/**
 * 检查音频是否已缓存
 * @param url 远程音频 URL
 * @returns true: 已缓存，false: 未缓存
 */
export async function audioIsCached(url: string): Promise<boolean> {
  return invoke("audio_is_cached", { url });
}

/**
 * 获取音频缓存统计信息
 * @returns 缓存文件数量、总大小等统计信息
 */
export async function audioGetStats(): Promise<AudioCacheStats> {
  return invoke("audio_get_stats");
}

/**
 * 清空音频缓存
 * @returns 清理的文件数量
 */
export async function audioClearCache(): Promise<number> {
  return invoke("audio_clear_cache");
}
