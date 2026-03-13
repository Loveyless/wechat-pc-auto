import { useDesktopShell } from "@/hooks/use-desktop-shell"
import { ShellConnectionBanner } from "@/components/shell/shell-connection-banner"
import { MessageStreamPane } from "@/components/shell/message-stream-pane"
import { RuntimeOverviewPanel } from "@/components/shell/runtime-overview-panel"
import { SessionListPane } from "@/components/shell/session-list-pane"
import { resolveDataEmptyState } from "@/components/shell/shell-view-model"

export function DesktopShell() {
  const shell = useDesktopShell()
  const dataEmptyState = resolveDataEmptyState({
    connectionState: shell.connectionState,
    sessionCount: shell.sessions.length,
    selectedSessionId: shell.selectedSessionId,
    selectedMessageCount: shell.selectedMessages.length,
  })

  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="mx-auto flex min-h-screen max-w-[1520px] flex-col gap-6 px-5 py-6 lg:px-6">
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

        <section className="grid flex-1 gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
          <SessionListPane
            sessions={shell.sessions}
            selectedSessionId={shell.selectedSessionId}
            showNoSessionsState={dataEmptyState === "no-sessions"}
            onSelect={(sessionId) => {
              void shell.selectSession(sessionId)
            }}
          />
          <MessageStreamPane
            sessions={shell.sessions}
            selectedSessionId={shell.selectedSessionId}
            selectedMessages={shell.selectedMessages}
            emptyState={dataEmptyState}
          />
        </section>
      </div>
    </main>
  )
}
