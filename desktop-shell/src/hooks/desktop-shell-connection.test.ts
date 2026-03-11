import { describe, expect, it } from "vitest"

import type { BackendConnectionInfo } from "@/lib/api"

import {
  resolveConnectAttemptState,
  resolveFailureConnectionState,
  resolveHydrationConnectionState,
  shouldUseStartupState,
} from "./desktop-shell-connection"

const managedInfo: BackendConnectionInfo = {
  httpBaseUrl: "http://127.0.0.1:8765",
  wsUrl: "ws://127.0.0.1:8766/events",
  managed: true,
  startupError: "",
  runtimeRoot: "C:/runtime",
}

const unmanagedInfo: BackendConnectionInfo = {
  ...managedInfo,
  managed: false,
}

describe("desktop shell connection state", () => {
  it("marks cold-start managed backend as starting", () => {
    expect(shouldUseStartupState(managedInfo, false)).toBe(true)
    expect(resolveHydrationConnectionState(managedInfo, false)).toBe("starting")
  })

  it("does not reuse startup state after a successful connection", () => {
    expect(shouldUseStartupState(managedInfo, true)).toBe(false)
    expect(resolveHydrationConnectionState(managedInfo, true)).toBeNull()
  })

  it("keeps first connection attempts in loading and reconnect attempts in reconnecting", () => {
    expect(resolveConnectAttemptState(false, false)).toBe("loading")
    expect(resolveConnectAttemptState(true, true)).toBe("reconnecting")
  })

  it("distinguishes startup failure from degraded reconnect state", () => {
    expect(resolveFailureConnectionState(managedInfo, false, true)).toBe("startup_failed")
    expect(resolveFailureConnectionState(managedInfo, true, true)).toBe("degraded")
  })

  it("keeps cold-start retries in starting but degrades unmanaged cold starts", () => {
    expect(resolveFailureConnectionState(managedInfo, false, false)).toBe("starting")
    expect(resolveFailureConnectionState(unmanagedInfo, false, false)).toBe("degraded")
    expect(resolveFailureConnectionState(managedInfo, true, false)).toBe("reconnecting")
  })
})
