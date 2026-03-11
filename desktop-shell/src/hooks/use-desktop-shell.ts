import { useCallback, useEffect, useMemo, useRef, useState } from "react"

import {
  type BackendConnectionInfo,
  ManagedBackendStartupError,
  createEventSocket,
  fetchSessionMessages,
  fetchSessions,
  fetchSnapshot,
  resolveBackendConnectionInfo,
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

const DEFAULT_BACKEND_INFO: BackendConnectionInfo = {
  httpBaseUrl: import.meta.env.VITE_BACKEND_HTTP_URL ?? "http://127.0.0.1:8765",
  wsUrl: import.meta.env.VITE_BACKEND_WS_URL ?? "ws://127.0.0.1:8766/events",
  managed: false,
  startupError: "",
  runtimeRoot: "",
}

function shouldUseStartupState(
  backendInfo: BackendConnectionInfo,
  hasConnected: boolean,
): boolean {
  return backendInfo.managed && !hasConnected
}

function resolveFailureConnectionState(
  backendInfo: BackendConnectionInfo,
  hasConnected: boolean,
  fatal: boolean,
): ShellConnectionState {
  if (fatal) {
    return hasConnected ? "degraded" : "startup_failed"
  }
  if (shouldUseStartupState(backendInfo, hasConnected)) {
    return "starting"
  }
  return hasConnected ? "reconnecting" : "degraded"
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
  const [backendInfo, setBackendInfo] = useState<BackendConnectionInfo>(DEFAULT_BACKEND_INFO)
  const selectedSessionIdRef = useRef(selectedSessionId)
  const sessionOrderRef = useRef(runtimeState.session_order)
  const reconnectTimerRef = useRef<number | null>(null)
  const socketRef = useRef<WebSocket | null>(null)
  const connectionAttemptRef = useRef(0)
  const hasConnectedRef = useRef(false)
  const backendInfoRef = useRef(DEFAULT_BACKEND_INFO)
  const unmountedRef = useRef(false)

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current !== null) {
      window.clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
  }, [])

  const closeSocket = useCallback(() => {
    const socket = socketRef.current
    socketRef.current = null
    if (!socket) {
      return
    }
    if (socket.readyState === WebSocket.CONNECTING || socket.readyState === WebSocket.OPEN) {
      socket.close()
    }
  }, [])

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

  const hydrateFromSnapshot = useCallback(
    async (attemptId: number, isReconnect = false) => {
      let connectionInfo = backendInfoRef.current
      try {
        connectionInfo = await resolveBackendConnectionInfo()
        if (unmountedRef.current || attemptId !== connectionAttemptRef.current) {
          return { ok: false, fatal: false }
        }
        backendInfoRef.current = connectionInfo
        setBackendInfo(connectionInfo)
        if (connectionInfo.startupError) {
          throw new ManagedBackendStartupError(connectionInfo.startupError)
        }
        if (shouldUseStartupState(connectionInfo, hasConnectedRef.current)) {
          setConnectionState("starting")
        }
        const [snapshot, backendSessions] = await Promise.all([fetchSnapshot(), fetchSessions()])
        if (unmountedRef.current || attemptId !== connectionAttemptRef.current) {
          return { ok: false, fatal: false }
        }
        const mappedSessions = backendSessions.map(mapSession)
        const nextSessionOrder =
          snapshot.runtime.session_order.length > 0
            ? snapshot.runtime.session_order
            : mappedSessions.map((session) => session.id)
        const initialSessionId =
          snapshot.runtime.active_session_id ||
          mappedSessions[0]?.id ||
          selectedSessionIdRef.current ||
          ""
        let initialMessages: ShellMessage[] = []
        if (initialSessionId) {
          const backendMessages = await fetchSessionMessages(initialSessionId)
          initialMessages = backendMessages.map(mapMessage)
        }
        if (unmountedRef.current || attemptId !== connectionAttemptRef.current) {
          return { ok: false, fatal: false }
        }
        sessionOrderRef.current = nextSessionOrder
        selectedSessionIdRef.current = initialSessionId
        setRuntimeState({
          ...snapshot.runtime,
          session_order: nextSessionOrder,
        })
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
        setLastError("")
        return { ok: true, fatal: false }
      } catch (error) {
        if (unmountedRef.current || attemptId !== connectionAttemptRef.current) {
          return { ok: false, fatal: false }
        }
        const fatal = error instanceof ManagedBackendStartupError
        setConnectionState(
          resolveFailureConnectionState(connectionInfo, hasConnectedRef.current, fatal),
        )
        setLastError(error instanceof Error ? error.message : String(error))
        return { ok: false, fatal }
      }
    },
    [],
  )

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
      const mappedSessions = event.payload.items.map(mapSession)
      const nextSessionOrder = mappedSessions.map((session) => session.id)
      sessionOrderRef.current = nextSessionOrder
      setRuntimeState((current) => ({
        ...current,
        session_order: nextSessionOrder,
      }))
      setSessions(mappedSessions)
      if (!selectedSessionIdRef.current && mappedSessions[0]?.id) {
        selectedSessionIdRef.current = mappedSessions[0].id
        setSelectedSessionId(mappedSessions[0].id)
      }
      return
    }
    if (event.event === "session.upsert") {
      setSessions((current) =>
        upsertSession(current, mapSession(event.payload), sessionOrderRef.current),
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
  }, [])

  const connect = useCallback(
    async function connect(isReconnect = false) {
      const attemptId = connectionAttemptRef.current + 1
      connectionAttemptRef.current = attemptId
      clearReconnectTimer()
      closeSocket()
      setConnectionState(hasConnectedRef.current && isReconnect ? "reconnecting" : "loading")
      const hydrated = await hydrateFromSnapshot(attemptId, isReconnect)
      if (unmountedRef.current || attemptId !== connectionAttemptRef.current) {
        return
      }
      if (!hydrated.ok) {
        if (hydrated.fatal) {
          return
        }
        reconnectTimerRef.current = window.setTimeout(() => {
          void connect(true)
        }, 1500)
        return
      }
      try {
        const socket = await createEventSocket((event) => {
          if (unmountedRef.current || attemptId !== connectionAttemptRef.current) {
            return
          }
          handleEvent(event)
        })
        if (unmountedRef.current || attemptId !== connectionAttemptRef.current) {
          if (socket.readyState === WebSocket.CONNECTING || socket.readyState === WebSocket.OPEN) {
            socket.close()
          }
          return
        }
        socketRef.current = socket
        socket.addEventListener("open", () => {
          if (unmountedRef.current || attemptId !== connectionAttemptRef.current) {
            return
          }
          hasConnectedRef.current = true
          setConnectionState("ready")
          setLastError("")
        })
        socket.addEventListener("close", () => {
          if (socketRef.current === socket) {
            socketRef.current = null
          }
          if (unmountedRef.current || attemptId !== connectionAttemptRef.current) {
            return
          }
          setConnectionState("reconnecting")
          clearReconnectTimer()
          reconnectTimerRef.current = window.setTimeout(() => {
            void connect(true)
          }, 1500)
        })
        socket.addEventListener("error", () => {
          if (unmountedRef.current || attemptId !== connectionAttemptRef.current) {
            return
          }
          setConnectionState("reconnecting")
        })
      } catch (error) {
        if (unmountedRef.current || attemptId !== connectionAttemptRef.current) {
          return
        }
        const fatal = error instanceof ManagedBackendStartupError
        setConnectionState(
          resolveFailureConnectionState(backendInfoRef.current, hasConnectedRef.current, fatal),
        )
        setLastError(error instanceof Error ? error.message : String(error))
        if (!fatal) {
          reconnectTimerRef.current = window.setTimeout(() => {
            void connect(true)
          }, 1500)
        }
      }
    },
    [clearReconnectTimer, closeSocket, handleEvent, hydrateFromSnapshot],
  )

  useEffect(() => {
    unmountedRef.current = false
    hasConnectedRef.current = false
    void connect(false)
    return () => {
      unmountedRef.current = true
      hasConnectedRef.current = false
      connectionAttemptRef.current += 1
      clearReconnectTimer()
      closeSocket()
    }
  }, [clearReconnectTimer, closeSocket, connect])

  const selectSession = useCallback(
    async (sessionId: string) => {
      selectedSessionIdRef.current = sessionId
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
    backendInfo,
  }
}
