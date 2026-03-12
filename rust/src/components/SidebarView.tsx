import { useRef, useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { listen } from "@tauri-apps/api/event";
import { convertFileSrc } from "@tauri-apps/api/core";
import { X, MessageCircle, Languages, AlertCircle, BookOpen, Users, User, Loader2 } from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Skeleton } from "@/components/ui/skeleton";
import { useSidebarStore } from "@/stores/sidebarStore";
import type { SidebarMessage, SidebarAppearance, AppSettings } from "@/lib/types";
import { useFormStore, type DisplayMode } from "@/stores/formStore";
import { useRuntimeStore } from "@/stores/runtimeStore";
import { useSettingsStore } from "@/stores/settingsStore";
import { SegmentedText } from "@/components/SegmentedText";
import { WordPopover } from "@/components/WordPopover";
import { WordBook } from "@/components/WordBook";
import * as api from "@/lib/tauri-api";

type WindowMode = "follow" | "independent";

function getWindowMode(): WindowMode {
  const params = new URLSearchParams(window.location.search);
  return params.get("mode") === "independent" ? "independent" : "follow";
}

function getDisplayCount(): number {
  const params = new URLSearchParams(window.location.search);
  const count = parseInt(params.get("count") || "3", 10);
  return Math.max(count, 1);
}

const DEFAULT_APPEARANCE: SidebarAppearance = {
  bg_opacity: 0.8,
  blur: "strong",
  card_style: "standard",
  text_enhance: "none",
};

function getAppearanceFromUrl(): SidebarAppearance {
  const params = new URLSearchParams(window.location.search);
  const b64 = params.get("appearance");
  if (b64) {
    try {
      return JSON.parse(atob(b64));
    } catch {
      return DEFAULT_APPEARANCE;
    }
  }
  return DEFAULT_APPEARANCE;
}

function getGhostModeFromUrl(): boolean {
  const params = new URLSearchParams(window.location.search);
  return params.get("ghost") === "true";
}

const BLUR_MAP: Record<string, string> = {
  none: "none",
  weak: "blur(8px) saturate(120%)",
  medium: "blur(14px) saturate(150%)",
  strong: "blur(20px) saturate(180%)",
};

const CARD_STYLE_MAP: Record<string, { bg: string; darkBg: string }> = {
  transparent: { bg: "rgba(255,255,255,0.1)", darkBg: "rgba(255,255,255,0.03)" },
  light: { bg: "rgba(245,246,248,0.5)", darkBg: "rgba(255,255,255,0.04)" },
  standard: { bg: "rgba(245,246,248,0.7)", darkBg: "rgba(255,255,255,0.05)" },
  dark: { bg: "rgba(230,232,236,0.9)", darkBg: "rgba(255,255,255,0.08)" },
};

function getTextEnhanceStyle(enhance: string): React.CSSProperties {
  switch (enhance) {
    case "shadow":
      return { textShadow: "0 1px 2px rgba(0,0,0,0.3)" };
    case "bold":
      return { fontWeight: 600 };
    default:
      return {};
  }
}

const DISPLAY_MODES: { value: DisplayMode; label: string; title: string }[] = [
  { value: "translated", label: "译", title: "纯翻译" },
  { value: "original", label: "中", title: "纯中文" },
  { value: "bilingual", label: "双", title: "双语混排" },
];

const containerVariants = {
  visible: { opacity: 1, x: 0, scale: 1 },
  hidden: { opacity: 0, x: -24, scale: 0.96 },
};

const containerTransition = {
  type: "spring" as const,
  stiffness: 380,
  damping: 28,
  mass: 0.8,
};

const SENDER_COLORS = [
  "bg-blue-400",
  "bg-amber-400",
  "bg-rose-400",
  "bg-violet-400",
  "bg-teal-400",
  "bg-orange-400",
  "bg-pink-400",
  "bg-cyan-400",
];

function getSenderColor(name: string): string {
  let hash = 0;
  for (const ch of name) hash = ((hash << 5) - hash + ch.charCodeAt(0)) | 0;
  return SENDER_COLORS[Math.abs(hash) % SENDER_COLORS.length];
}

function getInitialSystemDarkMode(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function useSidebarWindowAppearance() {
  const [isDarkMode, setIsDarkMode] = useState<boolean>(getInitialSystemDarkMode);
  const [isWindowFocused, setIsWindowFocused] = useState<boolean>(() => {
    if (typeof document === "undefined") return true;
    return document.hasFocus();
  });

  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");

    function onThemeChange(e: MediaQueryListEvent) {
      setIsDarkMode(e.matches);
    }

    function onFocus() {
      setIsWindowFocused(true);
    }

    function onBlur() {
      setIsWindowFocused(false);
    }

    setIsDarkMode(mq.matches);
    setIsWindowFocused(document.hasFocus());
    mq.addEventListener("change", onThemeChange);
    window.addEventListener("focus", onFocus);
    window.addEventListener("blur", onBlur);

    return () => {
      mq.removeEventListener("change", onThemeChange);
      window.removeEventListener("focus", onFocus);
      window.removeEventListener("blur", onBlur);
    };
  }, []);

  return { isDarkMode, isWindowFocused };
}

function renderMessageCard(
  msg: SidebarMessage,
  displayMode: DisplayMode,
  translatingIds: Set<number>,
  setTranslatingIds: React.Dispatch<React.SetStateAction<Set<number>>>
) {
  const hasSender = msg.sender !== "";
  const sender = msg.sender || msg.chatName;
  const color = getSenderColor(sender);

  const cardClass = msg.isSelf
    ? "sidebar-msg-card-self rounded-lg overflow-hidden transition-colors duration-100 max-w-[88%]"
    : "sidebar-msg-card rounded-lg overflow-hidden transition-colors duration-100";

  const wrapperClass = msg.isSelf ? "flex justify-end" : "";

  return (
    <motion.div
      key={msg.id}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.15, ease: "easeOut" }}
      className={wrapperClass}
    >
      <div className={cardClass}>
        <div className="px-3 py-2">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-1 min-w-0">
              {msg.isSelf ? (
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" />
              ) : hasSender ? (
                <>
                  <span className={`w-1.5 h-1.5 rounded-full ${color} shrink-0`} />
                </>
              ) : msg.chatType === "group" ? (
                <Users className="w-2.5 h-2.5 text-blue-400 dark:text-blue-500 shrink-0" />
              ) : msg.chatType === "private" ? (
                <User className="w-2.5 h-2.5 text-gray-400 dark:text-gray-500 shrink-0" />
              ) : (
                <MessageCircle className="w-2.5 h-2.5 text-gray-400 dark:text-gray-500 shrink-0" />
              )}
              <span className="text-[10px] font-medium text-gray-500 dark:text-gray-400 truncate">
                {msg.isSelf ? "我" : hasSender ? sender : ""}
              </span>
            </div>
            <span className="text-[9px] text-gray-300 dark:text-gray-600 tabular-nums shrink-0 ml-2">
              {msg.timestamp.slice(11, 19)}
            </span>
          </div>
          {msg.imagePath ? (
            <div className="mt-1">
              <img
                src={convertFileSrc(msg.imagePath)}
                alt="chat image"
                className="max-w-full max-h-48 rounded-md object-contain bg-black/5 dark:bg-white/5"
                loading="lazy"
              />
            </div>
          ) : displayMode === "translated" ? (
            // 译文模式：区分三种状态
            // 1. 已翻译：显示英文（可点词查词）
            // 2. 正在翻译中（5秒内的消息）：显示骨架屏，hover 可看中文
            // 3. 历史未翻译（超过5秒）：显示中文 + 翻译按钮
            (() => {
              // 已翻译：直接显示英文
              if (msg.textEn && msg.textEn !== msg.textCn) {
                return (
                  <SegmentedText
                    text={msg.textEn}
                    className="text-[12px] text-gray-800 dark:text-gray-200 leading-relaxed whitespace-pre-wrap break-words"
                  />
                );
              }
              
              // 判断是否是最近 5 秒内的消息（可能正在翻译中）
              const msgTime = new Date(msg.timestamp).getTime();
              const now = Date.now();
              const isRecent = (now - msgTime) < 5000;
              
              if (isRecent) {
                // 正在翻译中：显示骨架屏，hover 可看中文
                return (
                  <TooltipProvider delayDuration={200}>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <div className="cursor-pointer hover:opacity-70 transition-opacity inline-block">
                          <Skeleton className="h-3 w-32" />
                          {msg.textCn.length > 20 && <Skeleton className="h-3 w-24 mt-1.5" />}
                        </div>
                      </TooltipTrigger>
                      <TooltipContent 
                        side="top" 
                        className="max-w-xs px-2 py-1.5 text-xs bg-zinc-800 text-zinc-100 border-zinc-700"
                      >
                        <p className="whitespace-pre-wrap">{msg.textCn}</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                );
              }
              
              // 历史未翻译：显示中文 + 翻译按钮
              const isTranslating = translatingIds.has(msg.id);
              return (
                <div className="flex items-start gap-1.5">
                  <p className="text-[12px] text-gray-800 dark:text-gray-200 leading-relaxed whitespace-pre-wrap break-words flex-1">
                    {msg.textCn}
                  </p>
                  <TooltipProvider delayDuration={200}>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <button 
                          className="shrink-0 mt-0.5 p-1 rounded hover:bg-gray-200/50 dark:hover:bg-white/10 transition-colors cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
                          disabled={isTranslating}
                          onClick={async (e) => {
                            e.stopPropagation();
                            if (isTranslating) return;
                            console.log("[Sidebar] 点击翻译按钮", {
                              messageId: msg.id,
                              chatName: msg.chatName,
                              sender: msg.sender,
                              content: msg.textCn.substring(0, 50),
                            });
                            setTranslatingIds(prev => new Set(prev).add(msg.id));
                            try {
                              await api.translateSidebarMessage({
                                messageId: msg.id,
                                chatName: msg.chatName,
                                sender: msg.sender,
                                content: msg.textCn,
                                detectedAt: msg.timestamp,
                              });
                              console.log("[Sidebar] 翻译请求发送成功");
                            } catch (err) {
                              console.error("[Sidebar] 翻译请求失败", err);
                              setTranslatingIds(prev => {
                                const next = new Set(prev);
                                next.delete(msg.id);
                                return next;
                              });
                            }
                          }}
                        >
                          {isTranslating ? (
                            <Loader2 className="w-3 h-3 text-gray-400 dark:text-gray-500 animate-spin" />
                          ) : (
                            <Languages className="w-3 h-3 text-gray-400 dark:text-gray-500" />
                          )}
                        </button>
                      </TooltipTrigger>
                      <TooltipContent side="left" className="text-xs">
                        {isTranslating ? "翻译中..." : "点击翻译"}
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
              );
            })()
          ) : displayMode === "original" ? (
            <p className="text-[12px] text-gray-800 dark:text-gray-200 leading-relaxed whitespace-pre-wrap break-words">
              {msg.textCn}
            </p>
          ) : (
            <>
              <p className="text-[12px] text-gray-800 dark:text-gray-200 leading-relaxed whitespace-pre-wrap break-words">
                {msg.textCn}
              </p>
              {msg.textEn && msg.textEn !== msg.textCn && (
                <div className="mt-1 pt-1 border-t border-dashed border-gray-200/60 dark:border-white/[0.06] flex gap-1.5 items-start">
                  <Languages className="w-3 h-3 text-sky-400/40 dark:text-sky-400/25 shrink-0 mt-0.5" />
                  <p className="text-[11px] text-sky-700/50 dark:text-sky-300/40 leading-relaxed whitespace-pre-wrap break-words">
                    {msg.textEn}
                  </p>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </motion.div>
  );
}

export function SidebarView() {
  const { isDarkMode, isWindowFocused } = useSidebarWindowAppearance();

  const [windowMode] = useState<WindowMode>(getWindowMode);
  const isIndependent = windowMode === "independent";
  const displayCount = isIndependent ? getDisplayCount() : 0;
  const [appearance, setAppearance] = useState<SidebarAppearance>(getAppearanceFromUrl);
  const [ghostMode, setGhostMode] = useState<boolean>(getGhostModeFromUrl);

  useEffect(() => {
    document.documentElement.style.background = "transparent";
    document.body.style.background = "transparent";
  }, []);

  // 监听配置变更事件，实时更新外观和隐身模式
  useEffect(() => {
    const unlisten = listen<AppSettings>("settings-updated", (e) => {
      if (e.payload.display?.sidebar_appearance) {
        setAppearance(e.payload.display.sidebar_appearance);
      }
      if (e.payload.display?.ghost_mode !== undefined) {
        setGhostMode(e.payload.display.ghost_mode);
      }
    });
    return () => {
      unlisten.then((fn) => fn());
    };
  }, []);

  const items = useSidebarStore((s) => s.items);
  const currentChat = useSidebarStore((s) => s.currentChat);
  const refreshVersion = useSidebarStore((s) => s.refreshVersion);
  const hydrateSnapshot = useSidebarStore((s) => s.hydrateSnapshot);
  const updateMessageTranslation = useSidebarStore((s) => s.updateMessageTranslation);
  const displayMode = useFormStore((s) => s.displayMode);
  const setSettings = useFormStore((s) => s.setSettings);
  const settings = useSettingsStore((s) => s.settings);
  const translatorStatus = useRuntimeStore((s) => s.runtime.translator);
  const setTranslatorStatus = useRuntimeStore((s) => s.setTranslatorStatus);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(true);
  const [snapshotLoading, setSnapshotLoading] = useState(false);
  const [showWordBook, setShowWordBook] = useState(false);
  const [translatingIds, setTranslatingIds] = useState<Set<number>>(new Set());
  const translateEnabled = settings?.translate.enabled ?? false;
  const deeplxUrl = settings?.translate.deeplx_url ?? "";
  const canSwitchDisplayMode = !settings || (translateEnabled && deeplxUrl.trim() !== "");
  const effectiveDisplayMode: DisplayMode = canSwitchDisplayMode ? displayMode : "original";

  const fetchSnapshot = useCallback(async () => {
    setSnapshotLoading(true);
    try {
      const resp = await api.sidebarSnapshotGet({
        chatName: currentChat || undefined,
        limit: 50,
      });
      if (resp.data) {
        hydrateSnapshot(
          resp.data.current_chat ?? "",
          resp.data.messages ?? [],
          resp.data.refresh_version
        );
        setTranslatorStatus(resp.data.translator);
      }
    } catch {
      /* ignore */
    } finally {
      setSnapshotLoading(false);
    }
  }, [currentChat, hydrateSnapshot, setTranslatorStatus]);

  useEffect(() => {
    fetchSnapshot();
  }, [fetchSnapshot, refreshVersion]);

  useEffect(() => {
    if (isIndependent) return;
    const unlisten = listen<boolean>("sidebar-visibility", (e) => {
      setVisible(e.payload);
    });
    return () => {
      unlisten.then((fn) => fn());
    };
  }, [isIndependent]);

  // 监听单条消息翻译更新事件
  useEffect(() => {
    const unlisten = listen<{
      type: string;
      source: string;
      payload: {
        kind: string;
        message_id: number;
        chat_name: string;
        text_en: string;
        translate_error: string;
      };
    }>("wechat-event", (e) => {
      console.log("[Sidebar] 收到事件", e.payload);
      if (e.payload.type === "message" && e.payload.source === "sidebar" && e.payload.payload.kind === "update") {
        console.log("[Sidebar] 更新消息翻译", {
          messageId: e.payload.payload.message_id,
          textEn: e.payload.payload.text_en.substring(0, 50),
        });
        updateMessageTranslation(
          e.payload.payload.message_id,
          e.payload.payload.text_en,
          e.payload.payload.translate_error
        );
        setTranslatingIds(prev => {
          const next = new Set(prev);
          next.delete(e.payload.payload.message_id);
          return next;
        });
      }
    });
    return () => {
      unlisten.then((fn) => fn());
    };
  }, [updateMessageTranslation]);

  // 滚动到底部：当消息数量变化或最后一条消息内容更新时触发（仅跟随模式）
  // 这样翻译完成后内容增多也会自动滚动到底部
  const lastItemContent = items.length > 0 ? items[items.length - 1]?.textEn : "";
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [items.length, lastItemContent]);

  function handleClose() {
    api.sidebarStop().catch(() => {});
  }

  const textStyle = getTextEnhanceStyle(appearance.text_enhance);
  // cardBg 和 CARD_STYLE_MAP 可用于未来消息卡片样式自定义
  void CARD_STYLE_MAP;

  return (
    <motion.div
      variants={containerVariants}
      initial="visible"
      animate={visible ? "visible" : "hidden"}
      transition={containerTransition}
      data-window-focus={isWindowFocused ? "true" : "false"}
      className={`${isDarkMode ? "dark " : ""}relative flex flex-col h-screen overflow-hidden select-none`}
    >
      {/* 背景层 - 独立透明度控制 */}
      <div
        className="absolute inset-0 border border-[var(--sidebar-window-border)] rounded-lg"
        style={{
          opacity: appearance.bg_opacity,
          background: isDarkMode ? "rgba(18, 20, 26, 1)" : "rgba(255, 255, 255, 1)",
          backdropFilter: BLUR_MAP[appearance.blur],
          WebkitBackdropFilter: BLUR_MAP[appearance.blur],
        }}
      />

      {/* 内容层 - 始终不透明 */}
      <div className="relative z-10 flex flex-col h-full" style={textStyle}>
        {/* Title bar - 背景跟随窗口透明度 */}
        <div
          data-tauri-drag-region
          data-window-focus={isWindowFocused ? "true" : "false"}
          className="flex items-center justify-between px-3 py-2 shrink-0 border-b border-[var(--sidebar-window-border)]"
          style={ghostMode ? {} : {
            background: isDarkMode 
              ? `rgba(28, 30, 38, ${appearance.bg_opacity * 0.85})`
              : `rgba(255, 255, 255, ${appearance.bg_opacity * 0.85})`,
            backdropFilter: BLUR_MAP[appearance.blur],
            WebkitBackdropFilter: BLUR_MAP[appearance.blur],
          }}
        >
        <div data-tauri-drag-region className="flex items-center gap-1.5 flex-1 min-w-0">
          {(() => {
            const chatType = items[0]?.chatType;
            if (chatType === "group") {
              return <Users className="w-3.5 h-3.5 text-blue-500 dark:text-blue-400 shrink-0 pointer-events-none" />;
            } else if (chatType === "private") {
              return <User className="w-3.5 h-3.5 text-gray-500 dark:text-gray-400 shrink-0 pointer-events-none" />;
            }
            return <MessageCircle className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 shrink-0 pointer-events-none" />;
          })()}
          <span
            data-tauri-drag-region
            className="text-xs font-medium text-gray-700 dark:text-gray-300 truncate"
          >
            {currentChat || "等待聊天..."}
          </span>
        </div>
        {/* 隐身模式下隐藏所有按钮 */}
        {!ghostMode && (
          <div className="flex items-center gap-1 shrink-0">
            {canSwitchDisplayMode && (
              <div className="sidebar-mode-switch flex items-center h-5 rounded-md p-0.5">
                {DISPLAY_MODES.map((mode) => (
                  <button
                    key={mode.value}
                    onClick={() => setSettings({ displayMode: mode.value })}
                    title={mode.title}
                    className={`px-1.5 h-4 rounded text-[9px] font-medium transition-all duration-150 ${
                      effectiveDisplayMode === mode.value
                        ? "sidebar-mode-button-active shadow-sm"
                        : "sidebar-mode-button"
                    }`}
                  >
                    {mode.label}
                  </button>
                ))}
              </div>
            )}
            {/* 单词本按钮 - 仅跟随模式显示 */}
            {!isIndependent && (
              <button
                onClick={() => setShowWordBook(!showWordBook)}
                className={`w-6 h-6 flex items-center justify-center rounded-md transition-colors ${
                  showWordBook
                    ? "bg-primary/10 text-primary"
                    : "hover:bg-black/[0.05] dark:hover:bg-white/[0.08]"
                }`}
                title="单词本"
              >
                <BookOpen className={`w-3 h-3 ${showWordBook ? "text-primary" : "text-gray-400 dark:text-gray-500"}`} />
              </button>
            )}
            <button
              onClick={handleClose}
              className="w-6 h-6 flex items-center justify-center rounded-md hover:bg-red-500/10 transition-colors group"
              title="关闭"
            >
              <X className="w-3 h-3 text-gray-400 dark:text-gray-500 group-hover:text-red-500" />
            </button>
          </div>
        )}
      </div>

      {/* 独立模式：显示最新 N 条消息 */}
      {isIndependent && items.length > 0 && (
        <div className="px-2.5 pt-1 pb-2 overflow-hidden">
          <div className="flex flex-col gap-1.5">
            {items
              .slice(-displayCount)
              .map((msg) => renderMessageCard(msg, effectiveDisplayMode, translatingIds, setTranslatingIds))}
          </div>
        </div>
      )}

      {/* 单词本视图 - 仅跟随模式 */}
      {!isIndependent && showWordBook && (
        <div className="flex-1 overflow-hidden bg-background">
          <WordBook />
        </div>
      )}

      {/* 跟随模式：完整消息列表 */}
      {!isIndependent && !showWordBook && (
        <div className="sidebar-scroll flex-1 overflow-y-auto px-2.5 pt-1 pb-4">
          {items.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full gap-3">
              <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-emerald-100 to-sky-100 dark:from-emerald-900/40 dark:to-sky-900/40 flex items-center justify-center">
                <MessageCircle className="w-6 h-6 text-emerald-500/60 dark:text-emerald-400/50" />
              </div>
              <div className="text-center">
                <p className="text-xs text-gray-500 dark:text-gray-400 font-medium">
                  {snapshotLoading ? "加载消息中..." : "等待新消息..."}
                </p>
                <p className="text-[10px] text-gray-400/70 dark:text-gray-500/60 mt-1">
                  {snapshotLoading ? "正在从数据库同步当前聊天" : "切换微信聊天窗口即可开始"}
                </p>
              </div>
            </div>
          )}

          {settings && translateEnabled && !deeplxUrl.trim() && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 mb-2 rounded-lg bg-amber-500/5 dark:bg-amber-500/5">
              <AlertCircle className="w-3 h-3 text-amber-500 shrink-0" />
              <span className="text-[10px] text-amber-700 dark:text-amber-300 italic truncate">
                翻译未配置，当前只显示原文
              </span>
            </div>
          )}

          {translatorStatus.last_error && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 mb-2 rounded-lg bg-red-500/5 dark:bg-red-500/5">
              <AlertCircle className="w-3 h-3 text-red-500 shrink-0" />
              <span className="text-[10px] text-red-600 dark:text-red-300 italic truncate">
                {translatorStatus.last_error}
              </span>
            </div>
          )}

          <div className="flex flex-col gap-1.5">
            <AnimatePresence initial={false}>
              {items.map((msg) => renderMessageCard(msg, effectiveDisplayMode, translatingIds, setTranslatingIds))}
            </AnimatePresence>
          </div>
          <div ref={bottomRef} />
        </div>
      )}
      
      {/* 单词查词弹窗 */}
      <WordPopover />
      </div>
    </motion.div>
  );
}
