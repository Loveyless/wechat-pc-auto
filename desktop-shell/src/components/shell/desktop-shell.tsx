import { Button } from "@/components/ui/button"
import { StatusBadge } from "@/components/ui/status-badge"
import { mockMessages, mockSessions } from "@/data/mock-shell"

function SessionListPane() {
  return (
    <aside className="flex h-full flex-col rounded-3xl border border-border bg-card/90 p-4 shadow-sm">
      <div className="mb-4 space-y-1">
        <p className="text-sm font-medium text-muted-foreground">会话列表</p>
        <p className="text-xs text-muted-foreground">
          Phase 1 静态骨架：后续从 <code>/api/sessions</code> 引导，并订阅
          <code className="ml-1">session.list.updated</code>。
        </p>
      </div>

      <div className="space-y-2">
        {mockSessions.map((session, index) => {
          const selected = index === 0

          return (
            <button
              key={session.id}
              className={[
                "w-full rounded-2xl border px-4 py-3 text-left transition",
                selected
                  ? "border-primary/50 bg-primary/10 shadow-sm"
                  : "border-border bg-background hover:border-primary/30 hover:bg-accent/40",
              ].join(" ")}
              type="button"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="truncate font-medium">{session.name}</span>
                    <StatusBadge tone={session.kind === "group" ? "neutral" : "accent"}>
                      {session.kind === "group" ? "群聊" : "私聊"}
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

function MessageStreamPane() {
  return (
    <section className="flex h-full flex-col rounded-3xl border border-border bg-card/90 p-5 shadow-sm">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4">
        <div className="space-y-1">
          <p className="text-sm text-muted-foreground">当前会话</p>
          <h2 className="text-2xl font-semibold tracking-tight">英语打卡群</h2>
          <p className="text-sm text-muted-foreground">按会话分组，点左侧切换消息流。</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge tone="accent">preview_only</StatusBadge>
          <StatusBadge tone="accent">all_sessions</StatusBadge>
          <StatusBadge tone="neutral">TTS autoplay 保留后端语义</StatusBadge>
        </div>
      </div>

      <div className="grid gap-4">
        {mockMessages.map((message) => (
          <article key={message.id} className="rounded-2xl border border-border bg-background/80 p-4">
            <div className="mb-3 flex items-center justify-between gap-4">
              <div className="space-y-1">
                <p className="text-sm font-medium">{message.sender}</p>
                <p className="text-xs text-muted-foreground">{message.time}</p>
              </div>
              <StatusBadge tone="neutral">translated</StatusBadge>
            </div>

            <p className="text-base font-medium leading-7">{message.translated}</p>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              原始预览：{message.original}
            </p>
          </article>
        ))}
      </div>
    </section>
  )
}

export function DesktopShell() {
  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="mx-auto flex min-h-screen max-w-7xl flex-col gap-6 px-6 py-6">
        <header className="flex flex-wrap items-center justify-between gap-4 rounded-3xl border border-border bg-card/90 px-5 py-4 shadow-sm">
          <div className="space-y-1">
            <p className="text-sm text-muted-foreground">04-01 · Tauri + React + TypeScript + shadcn/ui</p>
            <h1 className="text-3xl font-semibold tracking-tight">WeChat Auto Desktop Shell</h1>
            <p className="text-sm text-muted-foreground">
              现在只是静态骨架，后续接 Python 本地 <code>HTTP + WebSocket</code>。
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button variant="secondary">HTTP Bootstrap</Button>
            <Button>WS Live Stream</Button>
          </div>
        </header>

        <section className="grid flex-1 gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
          <SessionListPane />
          <MessageStreamPane />
        </section>
      </div>
    </main>
  )
}
