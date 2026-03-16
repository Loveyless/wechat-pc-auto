import { useEffect, useState, useSyncExternalStore } from "react"

import { Button } from "@/components/ui/button"
import { StatusBadge } from "@/components/ui/status-badge"
import { useDesktopShell } from "@/hooks/use-desktop-shell"
import { useDesktopSettings } from "@/hooks/use-desktop-settings"
import { ShellConnectionBanner } from "@/components/shell/shell-connection-banner"
import { MessageStreamPane } from "@/components/shell/message-stream-pane"
import { RuntimeOverviewPanel } from "@/components/shell/runtime-overview-panel"
import { SettingsWorkspace } from "@/components/shell/settings-workspace"
import { SessionListPane } from "@/components/shell/session-list-pane"
import {
  resolveConnectionOverviewState,
  resolveDataEmptyState,
} from "@/components/shell/shell-view-model"

const DEFAULT_VIEWPORT_WIDTH = 1440
const SIDEBAR_WIDTH = 280
const ULTRA_COMPACT_WIDTH = 200
const COMPACT_SIDEBAR_GUTTER = 12

function subscribeViewportWidth(onStoreChange: () => void) {
  if (typeof window === "undefined") {
    return () => undefined
  }

  window.addEventListener("resize", onStoreChange)
  return () => {
    window.removeEventListener("resize", onStoreChange)
  }
}

function getViewportWidth() {
  if (typeof window === "undefined") {
    return DEFAULT_VIEWPORT_WIDTH
  }

  return window.innerWidth
}

export function DesktopShell() {
  const shell = useDesktopShell()
  const viewportWidth = useSyncExternalStore(
    subscribeViewportWidth,
    getViewportWidth,
    () => DEFAULT_VIEWPORT_WIDTH,
  )
  const isUltraCompact = viewportWidth < ULTRA_COMPACT_WIDTH
  const compactSidebarWidth = Math.max(
    0,
    Math.min(SIDEBAR_WIDTH, viewportWidth - COMPACT_SIDEBAR_GUTTER),
  )
  const [showStatusPanels, setShowStatusPanels] = useState(false)
  const [showOriginal, setShowOriginal] = useState(false)
  const [ttsTogglePending, setTtsTogglePending] = useState(false)
  const [desktopSidebarVisible, setDesktopSidebarVisible] = useState(true)
  const [compactSidebarVisible, setCompactSidebarVisible] = useState(false)
  const settings = useDesktopSettings(shell.backendInfo)
  const dataEmptyState = resolveDataEmptyState({
    connectionState: shell.connectionState,
    sessionCount: shell.sessions.length,
    selectedSessionId: shell.selectedSessionId,
    selectedMessageCount: shell.selectedMessages.length,
  })
  const overviewState = resolveConnectionOverviewState(
    shell.connectionState,
    shell.lastError,
  )
  const sidebarVisible = isUltraCompact ? compactSidebarVisible : desktopSidebarVisible
  const settingsPanelVisible = settings.isOpen

  useEffect(() => {
    if (!isUltraCompact) {
      setCompactSidebarVisible(false)
    }
  }, [isUltraCompact])

  const toggleSidebarVisibility = () => {
    if (isUltraCompact) {
      setCompactSidebarVisible((current) => !current)
      return
    }

    setDesktopSidebarVisible((current) => !current)
  }

  const sessionPane = (
    <SessionListPane
      sessions={shell.sessions}
      selectedSessionId={shell.selectedSessionId}
      showNoSessionsState={dataEmptyState === "no-sessions"}
      onSelect={(sessionId) => {
        if (isUltraCompact) {
          setCompactSidebarVisible(false)
        }
        void shell.selectSession(sessionId)
      }}
    />
  )

  const messagePane = (
    <MessageStreamPane
      sessions={shell.sessions}
      selectedSessionId={shell.selectedSessionId}
      selectedMessages={shell.selectedMessages}
      emptyState={dataEmptyState}
      showOriginal={showOriginal}
    />
  )

  const settingsPane = <SettingsWorkspace settings={settings} />

  return (
    <main className="h-screen overflow-hidden bg-background text-foreground">
      <div className="mx-auto flex h-full max-w-[1440px] flex-col gap-2 px-2 py-2 lg:px-3 lg:py-3">
        <section className="rounded-[1rem] border border-border-subtle bg-surface-panel-raised/92 px-3 py-2.5 shadow-[0_10px_24px_rgba(29,38,50,0.05)]">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="min-w-0">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
                功能区
              </p>
              <div className="mt-0.5 flex flex-wrap items-center gap-2">
                <h1 className="text-sm font-semibold text-text-primary">微信桌面监听</h1>
                <StatusBadge tone={overviewState.tone}>{overviewState.label}</StatusBadge>
                <span className="text-[12px] text-text-secondary">
                  会话 {shell.sessions.length}
                </span>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Button
                aria-controls="shell-session-pane"
                aria-expanded={sidebarVisible}
                aria-pressed={sidebarVisible}
                onClick={toggleSidebarVisibility}
                size="sm"
                variant={sidebarVisible ? "default" : "outline"}
              >
                {sidebarVisible ? "会话栏开" : "会话栏关"}
              </Button>
              <Button
                aria-pressed={showOriginal}
                onClick={() => {
                  setShowOriginal((current) => !current)
                }}
                size="sm"
                variant={showOriginal ? "default" : "outline"}
              >
                {showOriginal ? "原文开" : "原文关"}
              </Button>
              <Button
                aria-pressed={shell.ttsState.auto_read_enabled}
                disabled={ttsTogglePending}
                onClick={() => {
                  const nextEnabled = !shell.ttsState.auto_read_enabled
                  setTtsTogglePending(true)
                  void shell
                    .setTtsAutoReadEnabled(nextEnabled)
                    .finally(() => {
                      setTtsTogglePending(false)
                    })
                }}
                size="sm"
                variant={shell.ttsState.auto_read_enabled ? "default" : "outline"}
              >
                {shell.ttsState.auto_read_enabled ? "朗读开" : "朗读关"}
              </Button>
              <Button
                aria-controls="shell-status-panels"
                aria-expanded={showStatusPanels}
                onClick={() => {
                  setShowStatusPanels((current) => !current)
                }}
                size="sm"
                variant="outline"
              >
                {showStatusPanels ? "收起状态" : "展开状态"}
              </Button>
              <Button
                aria-controls="shell-settings-panel"
                aria-expanded={settingsPanelVisible}
                onClick={() => {
                  if (isUltraCompact) {
                    setCompactSidebarVisible(false)
                  }
                  if (settingsPanelVisible) {
                    settings.closeSettings()
                    return
                  }
                  void settings.openSettings()
                }}
                size="sm"
                variant={settingsPanelVisible ? "default" : "panel"}
              >
                {settings.isDirty ? "设置*" : "设置"}
              </Button>
            </div>
          </div>
        </section>

        {showStatusPanels ? (
          <div id="shell-status-panels" className="flex flex-col gap-2">
            <RuntimeOverviewPanel
              connectionState={shell.connectionState}
              runtimeState={shell.runtimeState}
              translationState={shell.translationState}
              ttsState={shell.ttsState}
              backendInfo={shell.backendInfo}
              lastEvent={shell.lastEvent}
              lastError={shell.lastError}
            />

            <ShellConnectionBanner
              connectionState={shell.connectionState}
              lastError={shell.lastError}
            />
          </div>
        ) : null}

        <section className="relative flex min-h-0 flex-1 overflow-hidden rounded-[1.3rem] border border-border-subtle bg-surface-panel-raised/95 shadow-[0_14px_34px_rgba(29,38,50,0.07)]">
          {!isUltraCompact && sidebarVisible ? (
            <div id="shell-session-pane" className="h-full w-[280px] shrink-0">
              {sessionPane}
            </div>
          ) : null}

          <div className="min-h-0 min-w-0 flex-1">{messagePane}</div>

          {!isUltraCompact && settingsPanelVisible ? (
            <div
              id="shell-settings-panel"
              className="h-full w-[420px] shrink-0 border-l border-border-subtle"
            >
              {settingsPane}
            </div>
          ) : null}

          {isUltraCompact && sidebarVisible ? (
            <>
              <button
                aria-label="关闭会话导航"
                className="absolute inset-0 z-10 bg-[rgba(29,38,50,0.18)]"
                onClick={() => {
                  setCompactSidebarVisible(false)
                }}
                type="button"
              />
              <div
                id="shell-session-pane"
                className="absolute inset-y-0 left-0 z-20 overflow-hidden shadow-[0_18px_36px_rgba(29,38,50,0.16)]"
                style={{ width: `${compactSidebarWidth}px` }}
              >
                {sessionPane}
              </div>
            </>
          ) : null}

          {isUltraCompact && settingsPanelVisible ? (
            <>
              <button
                aria-label="关闭设置面板"
                className="absolute inset-0 z-30 bg-[rgba(29,38,50,0.18)]"
                onClick={() => {
                  settings.closeSettings()
                }}
                type="button"
              />
              <div
                id="shell-settings-panel"
                className="absolute inset-y-0 right-0 z-40 w-[min(420px,calc(100vw-12px))] overflow-hidden border-l border-border-subtle shadow-[0_18px_36px_rgba(29,38,50,0.16)]"
              >
                {settingsPane}
              </div>
            </>
          ) : null}
        </section>
      </div>
    </main>
  )
}
