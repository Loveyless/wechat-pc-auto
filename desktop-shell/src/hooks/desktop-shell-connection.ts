import type { BackendConnectionInfo } from "@/lib/api"
import type { ShellConnectionState } from "@/lib/shell-types"

export function shouldUseStartupState(
  backendInfo: BackendConnectionInfo,
  hasConnected: boolean,
): boolean {
  return backendInfo.managed && !hasConnected
}

export function resolveConnectAttemptState(
  hasConnected: boolean,
  isReconnect: boolean,
): ShellConnectionState {
  return hasConnected && isReconnect ? "reconnecting" : "loading"
}

export function resolveHydrationConnectionState(
  backendInfo: BackendConnectionInfo,
  hasConnected: boolean,
): ShellConnectionState | null {
  return shouldUseStartupState(backendInfo, hasConnected) ? "starting" : null
}

export function resolveFailureConnectionState(
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
