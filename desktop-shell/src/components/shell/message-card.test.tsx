import { renderToStaticMarkup } from "react-dom/server"
import { describe, expect, it } from "vitest"

import { MessageCard } from "@/components/shell/message-card"
import type { ShellMessage } from "@/lib/shell-types"

function createMessage(overrides: Partial<ShellMessage> = {}): ShellMessage {
  return {
    id: "msg-1",
    sessionId: "session-1",
    sender: "张三",
    time: "10:00",
    translated: "HELLO",
    original: "你好",
    display: "HELLO",
    captureLevel: "preview",
    pendingTranslation: false,
    ...overrides,
  }
}

describe("message card", () => {
  it("renders spinner placeholder while translation is pending and original is hidden", () => {
    const markup = renderToStaticMarkup(
      <MessageCard
        message={createMessage({
          translated: "",
          original: "你好",
          display: "你好",
          pendingTranslation: true,
        })}
        showOriginal={false}
      />,
    )

    expect(markup).toContain("等待翻译…")
    expect(markup).toContain("animate-spin")
    expect(markup).not.toContain("你好")
    expect(markup).not.toContain("原始预览")
  })

  it("renders original chinese immediately while translation is pending when original is enabled", () => {
    const markup = renderToStaticMarkup(
      <MessageCard
        message={createMessage({
          translated: "",
          original: "你好",
          display: "你好",
          pendingTranslation: true,
        })}
        showOriginal
      />,
    )

    expect(markup).toContain("你好")
    expect(markup).toContain("翻译中")
    expect(markup).not.toContain("等待翻译…")
    expect(markup).not.toContain("原始预览")
  })

  it("renders translated content first and keeps original in secondary area when requested", () => {
    const markup = renderToStaticMarkup(
      <MessageCard
        message={createMessage({
          translated: "HELLO",
          original: "你好",
          display: "HELLO",
          pendingTranslation: false,
        })}
        showOriginal
      />,
    )

    expect(markup).toContain("HELLO")
    expect(markup).toContain("原始预览")
    expect(markup).toContain("你好")
  })
})
