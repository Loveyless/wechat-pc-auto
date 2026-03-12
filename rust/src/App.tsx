import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Settings,
  Database,
  Radio,
  ChevronRight,
  MonitorPlay,
  Square,
} from "lucide-react";
import { PreflightBar } from "@/components/PreflightBar";
import { SettingsPage } from "@/components/SettingsPage";
import { EventStream } from "@/components/EventStream";
import { ServiceLogs } from "@/components/ServiceLogs";
import { MessageHistory } from "@/components/MessageHistory";
import { SidebarView } from "@/components/SidebarView";
import { AboutDialog } from "@/components/AboutDialog";
import { useEventStore } from "@/stores/eventStore";
import { useToastStore } from "@/stores/toastStore";
import { useFormStore } from "@/stores/formStore";
import { useSettingsStore } from "@/stores/settingsStore";
import { useRuntimeStore } from "@/stores/runtimeStore";
import { initDictionaryEventListeners, cleanupDictionaryEventListeners } from "@/stores/dictionaryStore";
import * as api from "@/lib/tauri-api";
import type { TaskState, TranslatorServiceStatus } from "@/lib/types";

const isSidebarView =
  new URLSearchParams(window.location.search).get("view") === "sidebar";

export default function App() {
  const [loading, setLoading] = useState(!isSidebarView);
  const settings = useSettingsStore((s) => s.settings);

  useEffect(() => {
    const cleanupPromises = [
      useEventStore.getState().initEventListener(),
      useSettingsStore.getState().initSettingsListener(),
      useRuntimeStore.getState().initRuntimeListener(),
    ];

    // 初始化词典事件监听器
    initDictionaryEventListeners();

    // 主窗口必须等待后端配置加载完成
    if (!isSidebarView) {
      api
        .appStateGet()
        .then((resp) => {
          if (resp.data) {
            useSettingsStore.getState().setSettings(resp.data.settings);
            useRuntimeStore.getState().setRuntime(resp.data.runtime);
          }
        })
        .catch(() => {})
        .finally(() => setLoading(false));
    }

    return () => {
      cleanupPromises.forEach((cleanup) => {
        cleanup.then((fn) => fn());
      });
      cleanupDictionaryEventListeners();
    };
  }, []);

  // 侧边栏窗口：直接渲染，从 URL 读取配置
  if (isSidebarView) {
    return <SidebarView />;
  }

  // 主窗口：等待后端配置加载完成
  if (loading || !settings) {
    return (
      <div className="h-screen flex items-center justify-center bg-background">
        <div className="text-center space-y-3">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-sm text-muted-foreground">加载配置中...</p>
        </div>
      </div>
    );
  }

  return <MainApp />;
}

type PageKey = "settings" | "history" | "logs";

interface NavItem {
  key: PageKey;
  label: string;
  icon: React.ReactNode;
  taskKey?: keyof TaskState;
  beta?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { key: "settings", label: "设置", icon: <Settings className="w-[18px] h-[18px]" /> },
  { key: "history", label: "历史", icon: <Database className="w-[18px] h-[18px]" /> },
  { key: "logs", label: "日志", icon: <Radio className="w-[18px] h-[18px]" /> },
];

function getTranslatorChip(status: TranslatorServiceStatus) {
  if (!status.enabled) {
    return {
      label: "翻译未启用",
      className: "bg-muted text-muted-foreground",
      dotClass: "bg-muted-foreground/30",
    };
  }
  if (!status.configured) {
    return {
      label: "翻译未配置",
      className: "bg-amber-500/10 text-amber-700",
      dotClass: "bg-amber-500",
    };
  }
  if (status.checking) {
    return {
      label: "翻译检测中",
      className: "bg-sky-500/10 text-sky-700",
      dotClass: "bg-sky-500 animate-pulse",
    };
  }
  if (status.healthy === true) {
    return {
      label: "翻译可用",
      className: "bg-primary/10 text-primary",
      dotClass: "bg-primary animate-pulse",
    };
  }
  return {
    label: "翻译异常",
    className: "bg-red-500/10 text-red-600",
    dotClass: "bg-red-500",
  };
}

function MainApp() {
  const [page, setPage] = useState<PageKey>("settings");
  const [liveBusy, setLiveBusy] = useState(false);
  const toast = useToastStore((s) => s.toast);
  const showToast = useToastStore((s) => s.showToast);
  const taskState = useRuntimeStore((s) => s.runtime.tasks);
  const translatorStatus = useRuntimeStore((s) => s.runtime.translator);
  const settings = useSettingsStore((s) => s.settings);
  const imageCapture = useFormStore((s) => s.imageCapture);
  const sidebarWindowMode = useFormStore((s) => s.sidebarWindowMode);

  async function handleLiveToggle() {
    if (liveBusy) return;
    setLiveBusy(true);

    try {
      if (taskState.sidebar) {
        await api.sidebarStop();
        showToast("浮窗已关闭", true);
      } else {
        if (!settings) {
          showToast("配置尚未加载完成", false);
          return;
        }

        const fullUrl = settings.translate.deeplx_url.trim();
        const isAiProvider = settings.translate.provider === "ai";
        
        // 验证翻译配置
        if (settings.translate.enabled) {
          if (isAiProvider && !settings.translate.ai_api_key) {
            showToast("AI 翻译未配置 API Key，不能启用翻译", false);
            return;
          }
          if (!isAiProvider && !fullUrl) {
            showToast("DeepLX 地址未配置，不能启用翻译", false);
            return;
          }
        }

        await api.liveStart({
          translateEnabled: settings.translate.enabled,
          provider: settings.translate.provider,
          deeplxUrl: fullUrl,
          aiProviderId: settings.translate.ai_provider_id,
          aiModelId: settings.translate.ai_model_id,
          aiApiKey: settings.translate.ai_api_key,
          aiBaseUrl: settings.translate.ai_base_url,
          sourceLang: settings.translate.source_lang,
          targetLang: settings.translate.target_lang,
          timeoutSeconds: settings.translate.timeout_seconds,
          maxConcurrency: settings.translate.max_concurrency,
          maxRequestsPerSecond: settings.translate.max_requests_per_second,
          intervalSeconds: settings.listen.interval_seconds,
          imageCapture,
          windowMode: sidebarWindowMode,
        });
        showToast("实时浮窗已开启", true);
      }
    } catch (e) {
      showToast(`${e}`, false);
    } finally {
      setLiveBusy(false);
    }
  }

  const sidebarRunning = taskState.sidebar;
  const liveFrozen = !taskState.monitoring && sidebarRunning;
  const liveControlsVisible = taskState.monitoring || sidebarRunning;
  const translatorChip = getTranslatorChip(translatorStatus);

  return (
    <div className="h-screen flex overflow-hidden bg-background">
      <aside
        className="w-[200px] shrink-0 flex flex-col"
        style={{
          background: "var(--color-sidebar-bg)",
          color: "var(--color-sidebar-foreground)",
        }}
      >
        <div className="px-5 pt-6 pb-3">
          <h1 className="text-[15px] font-semibold text-white tracking-tight leading-tight">
            WeChat Translate
          </h1>
        </div>

        {liveControlsVisible && (
          <div className="px-3 pb-4">
            <button
              onClick={handleLiveToggle}
              disabled={liveBusy}
              className={`w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-[13px] font-semibold transition-all duration-200 ${
                sidebarRunning
                  ? "bg-red-500/90 hover:bg-red-500 text-white"
                  : "bg-emerald-500/90 hover:bg-emerald-500 text-white"
              } ${liveBusy ? "opacity-60" : ""}`}
            >
              {sidebarRunning ? (
                <>
                  <Square className="w-4 h-4" />
                  {liveBusy ? "关闭中..." : "关闭浮窗"}
                </>
              ) : (
                <>
                  <MonitorPlay className="w-4 h-4" />
                  {liveBusy ? "启动中..." : "开启实时浮窗"}
                </>
              )}
            </button>
            {sidebarRunning && (
              <div className="flex items-center justify-center gap-1.5 mt-2">
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    liveFrozen ? "bg-amber-400" : "bg-emerald-400 animate-pulse"
                  }`}
                />
                <span
                  className={`text-[10px] ${
                    liveFrozen ? "text-amber-300" : "text-emerald-400"
                  }`}
                >
                  {liveFrozen ? "监听已暂停" : "运行中"}
                </span>
              </div>
            )}
          </div>
        )}

        <nav className="flex-1 px-3 space-y-0.5">
          {NAV_ITEMS.map((item) => {
            const active = page === item.key;
            const running = item.taskKey && taskState[item.taskKey];
            return (
              <button
                key={item.key}
                onClick={() => setPage(item.key)}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-[13px] font-medium transition-all duration-150 group relative ${
                  active ? "text-white" : "hover:text-white/90"
                }`}
                style={active ? { background: "var(--color-sidebar-hover)" } : undefined}
              >
                {active && (
                  <motion.div
                    layoutId="nav-active"
                    className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full"
                    style={{ background: "var(--color-sidebar-active)" }}
                  />
                )}
                <span className="relative z-10 opacity-85 group-hover:opacity-100">
                  {item.icon}
                </span>
                <span className="relative z-10 flex-1 text-left">{item.label}</span>
                {running && (
                  <span className="relative z-10 w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                )}
                {item.beta && (
                  <span className="relative z-10 text-[9px] px-1.5 py-0.5 rounded-full bg-white/10 text-white/70">
                    Beta
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        <div className="px-3 py-2 border-t border-white/6">
          <AboutDialog />
        </div>

        <div className="px-4 py-4 border-t border-white/6">
          <div className={`inline-flex items-center gap-2 px-2.5 py-1.5 rounded-full text-[11px] font-medium ${translatorChip.className}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${translatorChip.dotClass}`} />
            {translatorChip.label}
          </div>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-5xl mx-auto px-8 py-8">
          <PreflightBar />

          <AnimatePresence>
            {toast && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 20 }}
                className={`fixed bottom-6 right-6 z-50 rounded-xl px-4 py-3 text-sm font-medium shadow-lg ${
                  toast.ok
                    ? "bg-primary/10 text-primary border border-primary/20 backdrop-blur-sm"
                    : "bg-red-500/10 text-red-600 border border-red-500/20 backdrop-blur-sm"
                }`}
              >
                {toast.text}
              </motion.div>
            )}
          </AnimatePresence>

          <div className="mb-6 flex items-center justify-between">
            <div>
              <h2 className="text-[24px] font-semibold tracking-tight">
                {NAV_ITEMS.find((i) => i.key === page)?.label}
              </h2>
              <p className="text-sm text-muted-foreground mt-1">
                {page === "settings" && "调整监听、翻译和浮窗参数"}
                {page === "history" && "查看消息历史与翻译结果"}
                {page === "logs" && "查看实时日志与系统输出"}
              </p>
            </div>

            <div className="flex items-center gap-3">
              {(["monitoring", "sidebar"] as const).map((key) => (
                <div
                  key={key}
                  className="inline-flex items-center gap-2 rounded-full px-3 py-1.5 bg-muted/50 text-[11px] font-medium"
                >
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      taskState[key] ? "bg-primary animate-pulse" : "bg-muted-foreground/30"
                    }`}
                  />
                  {key === "monitoring" ? "监听" : "浮窗"}
                </div>
              ))}
            </div>
          </div>

          <AnimatePresence mode="wait">
            <motion.div
              key={page}
              initial={{ opacity: 0, x: 12 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -12 }}
              transition={{ duration: 0.18 }}
            >
              {page === "settings" && <SettingsPage />}
              {page === "history" && <MessageHistory />}
              {page === "logs" && (
                <div className="space-y-6">
                  <EventStream />
                  <ServiceLogs />
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        </div>
      </main>

      <div className="absolute left-[200px] top-1/2 -translate-y-1/2 -translate-x-1/2 pointer-events-none">
        <div className="w-8 h-8 rounded-full bg-background border border-border shadow-sm flex items-center justify-center">
          <ChevronRight className="w-4 h-4 text-muted-foreground" />
        </div>
      </div>
    </div>
  );
}
