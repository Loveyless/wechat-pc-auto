import { Button } from "@/components/ui/button"
import { StatusBadge } from "@/components/ui/status-badge"
import { useDesktopShell } from "@/hooks/use-desktop-shell"

function SessionListPane({
  sessions,
  selectedSessionId,
  onSelect,
}: {
  sessions: ReturnType<typeof useDesktopShell>["sessions"]
  selectedSessionId: string
  onSelect: (sessionId: string) => void
}) {
  return (
    <aside className="flex h-full flex-col rounded-3xl border border-border bg-card/90 p-4 shadow-sm">
      <div className="mb-4 space-y-1">
        <p className="text-sm font-medium text-muted-foreground">会话列表</p>
        <p className="text-xs text-muted-foreground">
          先走 <code>/api/sessions</code> 引导，再订阅
          <code className="ml-1">session.list.updated</code>。
        </p>
      </div>

      <div className="space-y-2">
        {sessions.map((session) => {
          const selected = session.id === selectedSessionId

          return (
            <button
              key={session.id}
              className={[
                "w-full rounded-2xl border px-4 py-3 text-left transition",
                selected
                  ? "border-primary/50 bg-primary/10 shadow-sm"
                  : "border-border bg-background hover:border-primary/30 hover:bg-accent/40",
              ].join(" ")}
              onClick={() => onSelect(session.id)}
              type="button"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="truncate font-medium">{session.name}</span>
                    <StatusBadge tone={session.kind === "group" ? "neutral" : session.kind === "private" ? "accent" : "neutral"}>
                      {session.kind === "group" ? "群聊" : session.kind === "private" ? "私聊" : "未知"}
                    </StatusBadge>
                  </div>
                  <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">{session.preview}</p>
                </div>
                <StatusBadge tone={session.unread > 0 ? "primary" : "neutral"}>
                  {session.unread}
                </StatusBadge>
              </div>
            </button>
          )
        })}
      </div>
    </aside>
  )
}

function MessageStreamPane({
  sessions,
  selectedSessionId,
  selectedMessages,
  runtimeState,
  translationState,
  ttsState,
  connectionState,
  lastError,
  lastEvent,
  backendInfo,
}: Pick<
  ReturnType<typeof useDesktopShell>,
  | "sessions"
  | "selectedSessionId"
  | "selectedMessages"
  | "runtimeState"
  | "translationState"
  | "ttsState"
  | "connectionState"
  | "lastError"
  | "lastEvent"
  | "backendInfo"
>) {
  const selectedSession = sessions.find((session) => session.id === selectedSessionId)

  return (
    <section className="flex h-full flex-col rounded-3xl border border-border bg-card/90 p-5 shadow-sm">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4">
        <div className="space-y-1">
          <p className="text-sm text-muted-foreground">当前会话</p>
          <h2 className="text-2xl font-semibold tracking-tight">{selectedSession?.name ?? "未选择会话"}</h2>
          <p className="text-sm text-muted-foreground">按会话分组，点左侧切换消息流并同步 active session。</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge tone="accent">{runtimeState.message_fidelity}</StatusBadge>
          <StatusBadge tone="accent">{runtimeState.monitor_scope}</StatusBadge>
          <StatusBadge tone={connectionState === "ready" ? "primary" : connectionState === "starting" ? "accent" : "neutral"}>{connectionState}</StatusBadge>
          <StatusBadge tone="neutral">translate:{translationState.provider}</StatusBadge>
          <StatusBadge tone="neutral">tts:{ttsState.provider}</StatusBadge>
        </div>
      </div>

      <div className="mb-4 grid gap-3 rounded-2xl border border-border bg-background/60 p-4 text-sm text-muted-foreground md:grid-cols-2">
        <div>
          <p className="font-medium text-foreground">后端入口</p>
          <p>{backendInfo.httpBaseUrl}</p>
          <p>{backendInfo.wsUrl}</p>
        </div>
        <div>
          <p className="font-medium text-foreground">运行态</p>
          <p>worker: {runtimeState.worker_state}</p>
          <p>detail: {runtimeState.worker_detail || "n/a"}</p>
          <p>last event: {lastEvent || "n/a"}</p>
          <p>last error: {lastError || "n/a"}</p>
        </div>
      </div>

      <div className="grid gap-4">
        {selectedMessages.map((message) => (
          <article key={message.id} className="rounded-2xl border border-border bg-background/80 p-4">
            <div className="mb-3 flex items-center justify-between gap-4">
              <div className="space-y-1">
                <p className="text-sm font-medium">{message.sender}</p>
                <p className="text-xs text-muted-foreground">{message.time}</p>
              </div>
              <StatusBadge tone="neutral">{message.captureLevel}</StatusBadge>
            </div>

            <p className="text-base font-medium leading-7">{message.display || message.translated || message.original}</p>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              原始预览：{message.original}
            </p>
            {message.pendingTranslation ? (
              <p className="mt-2 text-xs text-amber-300">翻译中...</p>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  )
}

export function DesktopShell() {
  const shell = useDesktopShell()

  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="mx-auto flex min-h-screen max-w-7xl flex-col gap-6 px-6 py-6">
        <header className="flex flex-wrap items-center justify-between gap-4 rounded-3xl border border-border bg-card/90 px-5 py-4 shadow-sm">
          <div className="space-y-1">
            <p className="text-sm text-muted-foreground">04-01 · Tauri + React + TypeScript + shadcn/ui</p>
            <h1 className="text-3xl font-semibold tracking-tight">WeChat Auto Desktop Shell</h1>
            <p className="text-sm text-muted-foreground">
              已接 Python 本地 <code>HTTP + WebSocket</code>；后端挂掉时回退 mock 数据保住开发页。
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button variant="secondary">{shell.runtimeState.monitor_scope}</Button>
            <Button>{shell.connectionState}</Button>
          </div>
        </header>

        <section className="grid flex-1 gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
          <SessionListPane
            sessions={shell.sessions}
            selectedSessionId={shell.selectedSessionId}
            onSelect={(sessionId) => {
              void shell.selectSession(sessionId)
            }}
          />
          <MessageStreamPane
            sessions={shell.sessions}
            selectedSessionId={shell.selectedSessionId}
            selectedMessages={shell.selectedMessages}
            runtimeState={shell.runtimeState}
            translationState={shell.translationState}
            ttsState={shell.ttsState}
            connectionState={shell.connectionState}
            lastError={shell.lastError}
            lastEvent={shell.lastEvent}
            backendInfo={shell.backendInfo}
          />
        </section>
      </div>
    </main>
  )
}
