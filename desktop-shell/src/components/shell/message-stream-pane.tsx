import { useEffect, useMemo, useRef, useState } from "react"

import { MessageCard } from "@/components/shell/message-card"
import { ShellEmptyState } from "@/components/shell/shell-empty-state"
import { Button } from "@/components/ui/button"
import type { ShellDataEmptyState } from "@/components/shell/shell-view-model"
import type { ShellMessage, ShellSession } from "@/lib/shell-types"

const BOTTOM_LOCK_THRESHOLD_PX = 32

type MessageStreamPaneProps = {
  sessions: ShellSession[]
  selectedSessionId: string
  selectedMessages: ShellMessage[]
  emptyState: ShellDataEmptyState
  showOriginal: boolean
}

export function MessageStreamPane({
  sessions,
  selectedSessionId,
  selectedMessages,
  emptyState,
  showOriginal,
}: MessageStreamPaneProps) {
  const selectedSession = sessions.find((session) => session.id === selectedSessionId)
  const scrollContainerRef = useRef<HTMLDivElement | null>(null)
  const [isPinnedToBottom, setIsPinnedToBottom] = useState(true)
  const hasMessages = emptyState !== "no-sessions" && emptyState !== "no-messages"
  const lastMessageVersion = useMemo(() => {
    const lastMessage = selectedMessages[selectedMessages.length - 1]

    if (!lastMessage) {
      return ""
    }

    return [
      lastMessage.id,
      lastMessage.display,
      lastMessage.translated,
      lastMessage.original,
      lastMessage.pendingTranslation ? "pending" : "ready",
    ].join(":")
  }, [selectedMessages])

  const scrollToBottom = (behavior: ScrollBehavior = "auto") => {
    const scrollContainer = scrollContainerRef.current
    if (!scrollContainer) {
      return
    }

    scrollContainer.scrollTo({
      top: scrollContainer.scrollHeight,
      behavior,
    })
    setIsPinnedToBottom(true)
  }

  useEffect(() => {
    if (!hasMessages) {
      setIsPinnedToBottom(true)
      return
    }

    const frameId = window.requestAnimationFrame(() => {
      scrollToBottom("auto")
    })

    return () => {
      window.cancelAnimationFrame(frameId)
    }
  }, [selectedSessionId, hasMessages])

  useEffect(() => {
    if (!hasMessages || !isPinnedToBottom) {
      return
    }

    const frameId = window.requestAnimationFrame(() => {
      scrollToBottom("auto")
    })

    return () => {
      window.cancelAnimationFrame(frameId)
    }
  }, [hasMessages, isPinnedToBottom, lastMessageVersion, showOriginal, selectedMessages.length])

  const handleScroll = () => {
    const scrollContainer = scrollContainerRef.current
    if (!scrollContainer) {
      return
    }

    const distanceFromBottom =
      scrollContainer.scrollHeight - scrollContainer.scrollTop - scrollContainer.clientHeight

    setIsPinnedToBottom(distanceFromBottom <= BOTTOM_LOCK_THRESHOLD_PX)
  }

  return (
    <section className="flex h-full min-h-0 flex-col bg-surface-panel-raised/70">
      <div className="shrink-0 border-b border-border-subtle px-4 py-3">
        <div className="space-y-1">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
            消息阅读
          </p>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="truncate text-[21px] font-semibold tracking-[-0.03em] text-text-primary">
                  {selectedSession?.name ?? "未选择会话"}
                </h2>
                {selectedSession?.previewOnly ? (
                  <span className="rounded-full bg-state-preview-soft px-2.5 py-1 text-[11px] font-semibold text-state-preview">
                    预览模式
                  </span>
                ) : null}
              </div>
              <p className="mt-0.5 text-[12px] leading-5 text-text-secondary">
                译文优先展示，原始预览降为次级信息。
              </p>
            </div>
            <div className="rounded-[0.85rem] border border-border-subtle bg-workspace-canvas-strong/85 px-2.5 py-1.5 text-right">
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-muted">
                消息数
              </p>
              <p className="text-sm font-semibold text-text-primary">{selectedMessages.length}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="relative min-h-0 flex-1 overflow-hidden bg-workspace-canvas-strong/35">
        {emptyState === "no-sessions" ? (
          <div className="h-full px-3 py-3">
            <ShellEmptyState
              eyebrow="No Sessions"
              title="还没有会话可读"
              detail="当前消息阅读区会跟随左侧会话导航；没有会话时，不应该继续显示空壳卡片。"
              icon="◌"
            />
          </div>
        ) : emptyState === "no-messages" ? (
          <div className="h-full px-3 py-3">
            <ShellEmptyState
              eyebrow="No Messages"
              title={`“${selectedSession?.name ?? "当前会话"}” 暂无消息`}
              detail="会话已经选中，但当前还没有可展示的消息流；等下一次 hydrate 或事件推送即可。"
              icon="◍"
            />
          </div>
        ) : (
          <>
            <div
              ref={scrollContainerRef}
              className="shell-scrollbar h-full overflow-y-auto px-3 py-3 pr-1.5"
              onScroll={handleScroll}
            >
              <div className="flex flex-col gap-2">
                {selectedMessages.map((message) => (
                  <div key={message.id} className="flex">
                    <MessageCard message={message} showOriginal={showOriginal} />
                  </div>
                ))}
              </div>
            </div>

            {!isPinnedToBottom ? (
              <Button
                aria-label="滚动到最新消息"
                className="absolute right-4 bottom-4 h-9 w-9 rounded-full border border-border-strong bg-surface-panel-raised/96 p-0 text-lg shadow-[0_10px_20px_rgba(29,38,50,0.12)]"
                onClick={() => {
                  scrollToBottom("smooth")
                }}
                size="sm"
                variant="panel"
              >
                ↓
              </Button>
            ) : null}
          </>
        )}
      </div>
    </section>
  )
}
