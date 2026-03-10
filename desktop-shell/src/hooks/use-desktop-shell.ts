import { useCallback, useEffect, useMemo, useRef, useState } from "react"

import {
  createEventSocket,
  fetchSessionMessages,
  fetchSessions,
  fetchSnapshot,
  getHttpBaseUrl,
  getWsUrl,
  setActiveSession,
} from "@/lib/api"
import type {
  BackendEvent,
  BackendMessage,
  BackendRuntimeState,
  BackendTTSState,
  BackendTranslationState,
  ShellConnectionState,
  ShellMessage,
  ShellSession,
} from "@/lib/shell-types"
import {
  mockMessages,
  mockRuntimeState,
  mockSessions,
  mockTranslationState,
  mockTtsState,
} from "@/data/mock-shell"

function inferSessionKind(name: string): ShellSession["kind"] {
  if (!name) {
    return "unknown"
  }
  return /群|Group/i.test(name) ? "group" : "private"
}

function mapSession(session: {
  session_id: string
  session_name: string
  unread_count: number
  latest_preview: string
  updated_at: string
  has_preview_only_messages: boolean
}): ShellSession {
  return {
    id: session.session_id,
    kind: inferSessionKind(session.session_name),
    name: session.session_name,
    preview: session.latest_preview,
    unread: session.unread_count,
    updatedAt: session.updated_at,
    previewOnly: session.has_preview_only_messages,
  }
}

function mapMessage(message: BackendMessage): ShellMessage {
  return {
    id: message.message_id,
    sessionId: message.session_id,
    sender: message.sender_name || (message.is_self ? "self" : "unknown"),
    time: message.created_at,
    translated: message.text_translated,
    original: message.text_original,
    display: message.text_display,
    captureLevel: message.capture_level,
    pendingTranslation: message.pending_translation,
  }
}

function upsertSession(list: ShellSession[], incoming: ShellSession, order: string[]) {
  const byId = new Map(list.map((item) => [item.id, item]))
  byId.set(incoming.id, incoming)
  const next = Array.from(byId.values())
  next.sort((left, right) => {
    const leftIndex = order.indexOf(left.id)
    const rightIndex = order.indexOf(right.id)
    const safeLeft = leftIndex === -1 ? Number.MAX_SAFE_INTEGER : leftIndex
    const safeRight = rightIndex === -1 ? Number.MAX_SAFE_INTEGER : rightIndex
    return safeLeft - safeRight
  })
  return next
}

function upsertMessage(list: ShellMessage[], incoming: ShellMessage) {
  const existingIndex = list.findIndex((item) => item.id === incoming.id)
  if (existingIndex === -1) {
    return [...list, incoming]
  }
  const next = [...list]
  next[existingIndex] = incoming
  return next
}

export function useDesktopShell() {
  const [connectionState, setConnectionState] = useState<ShellConnectionState>("loading")
  const [runtimeState, setRuntimeState] = useState<BackendRuntimeState>(mockRuntimeState)
  const [translationState, setTranslationState] = useState<BackendTranslationState>(mockTranslationState)
  const [ttsState, setTtsState] = useState<BackendTTSState>(mockTtsState)
  const [sessions, setSessions] = useState<ShellSession[]>(mockSessions)
  const [messagesBySession, setMessagesBySession] = useState<Record<string, ShellMessage[]>>({
    [mockSessions[0].id]: mockMessages,
  })
  const [selectedSessionId, setSelectedSessionId] = useState<string>(mockSessions[0]?.id ?? "")
  const [lastError, setLastError] = useState("")
  const [lastEvent, setLastEvent] = useState("")
  const reconnectTimerRef = useRef<number | null>(null)
  const socketRef = useRef<WebSocket | null>(null)
  const unmountedRef = useRef(false)

  const replaceFromSnapshot = useCallback(
    async (isReconnect = false) => {
      try {
        const [snapshot, backendSessions] = await Promise.all([fetchSnapshot(), fetchSessions()])
        if (unmountedRef.current) {
          return
        }
        const mappedSessions = backendSessions.map(mapSession)
        const initialSessionId =
          snapshot.runtime.active_session_id || mappedSessions[0]?.id || selectedSessionId
        let initialMessages: ShellMessage[] = []
        if (initialSessionId) {
          const backendMessages = await fetchSessionMessages(initialSessionId)
          initialMessages = backendMessages.map(mapMessage)
        }
        setRuntimeState(snapshot.runtime)
        setTranslationState(snapshot.translation)
        setTtsState(snapshot.tts)
        setSessions(mappedSessions)
        setSelectedSessionId(initialSessionId)
        if (initialSessionId) {
          setMessagesBySession((current) => ({
            ...current,
            [initialSessionId]: initialMessages,
          }))
        }
        setConnectionState(isReconnect ? "ready" : "ready")
        setLastError("")
      } catch (error) {
        if (unmountedRef.current) {
          return
        }
        setConnectionState(isReconnect ? "reconnecting" : "degraded")
        setLastError(error instanceof Error ? error.message : String(error))
      }
    },
    [selectedSessionId],
  )

  const loadMessagesForSession = useCallback(async (sessionId: string) => {
    const backendMessages = await fetchSessionMessages(sessionId)
    if (unmountedRef.current) {
      return
    }
    setMessagesBySession((current) => ({
      ...current,
      [sessionId]: backendMessages.map(mapMessage),
    }))
  }, [])

  const handleEvent = useCallback((event: BackendEvent) => {
    setLastEvent(event.event)
    if (event.event === "backend.state") {
      setRuntimeState((current) => ({
        ...current,
        worker_state: event.payload.state,
        worker_detail: event.payload.detail,
      }))
      return
    }
    if (event.event === "session.list.updated") {
      setSessions(event.payload.items.map(mapSession))
      return
    }
    if (event.event === "session.upsert") {
      setSessions((current) =>
        upsertSession(current, mapSession(event.payload), runtimeState.session_order),
      )
      return
    }
    if (event.event === "message.created" || event.event === "translation.updated") {
      const message = mapMessage(event.payload)
      setMessagesBySession((current) => ({
        ...current,
        [message.sessionId]: upsertMessage(current[message.sessionId] ?? [], message),
      }))
      return
    }
    if (event.event === "tts.updated") {
      setTtsState((current) => ({
        ...current,
        last_error: event.payload.accepted ? "" : event.payload.detail,
      }))
      return
    }
    if (event.event === "error.reported") {
      setLastError(`${event.payload.source}: ${event.payload.message}`)
    }
  }, [runtimeState.session_order])

  useEffect(() => {
    unmountedRef.current = false
    const connect = async (isReconnect = false) => {
      await replaceFromSnapshot(isReconnect)
      if (unmountedRef.current) {
        return
      }
      const socket = createEventSocket(handleEvent)
      socketRef.current = socket
      socket.addEventListener("open", () => {
        if (!unmountedRef.current) {
          setConnectionState("ready")
        }
      })
      socket.addEventListener("close", () => {
        if (unmountedRef.current) {
          return
        }
        setConnectionState("reconnecting")
        reconnectTimerRef.current = window.setTimeout(() => {
          void connect(true)
        }, 1500)
      })
      socket.addEventListener("error", () => {
        if (!unmountedRef.current) {
          setConnectionState("reconnecting")
        }
      })
    }

    void connect(false)
    return () => {
      unmountedRef.current = true
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current)
      }
      socketRef.current?.close()
    }
  }, [handleEvent, replaceFromSnapshot])

  const selectSession = useCallback(
    async (sessionId: string) => {
      setSelectedSessionId(sessionId)
      setRuntimeState((current) => ({
        ...current,
        active_session_id: sessionId,
      }))
      try {
        await setActiveSession(sessionId)
        await loadMessagesForSession(sessionId)
      } catch (error) {
        setLastError(error instanceof Error ? error.message : String(error))
      }
    },
    [loadMessagesForSession],
  )

  const selectedMessages = useMemo(() => {
    return messagesBySession[selectedSessionId] ?? []
  }, [messagesBySession, selectedSessionId])

  return {
    connectionState,
    runtimeState,
    translationState,
    ttsState,
    sessions,
    selectedSessionId,
    selectedMessages,
    lastError,
    lastEvent,
    selectSession,
    backendInfo: {
      httpBaseUrl: getHttpBaseUrl(),
      wsUrl: getWsUrl(),
    },
  }
}
