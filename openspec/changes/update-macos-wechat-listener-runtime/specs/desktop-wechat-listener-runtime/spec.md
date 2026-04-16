## ADDED Requirements

### Requirement: Desktop runtime SHALL read visible WeChat session previews on Apple Silicon macOS
The system SHALL, on `Apple Silicon / arm64 macOS`, read the visible left-side WeChat session list through a macOS-compatible window and Accessibility path and SHALL treat that left-side session preview list as the only supported truth source for the listener runtime. The shipped path SHALL continue to produce preview-only session data instead of switching to right-side full-message capture by default.

#### Scenario: WeChat is running and Accessibility access is granted
- **WHEN** the listener worker starts on macOS and the WeChat main window plus Accessibility tree are available
- **THEN** it reads the visible session list and produces preview snapshots that remain compatible with the existing `chat_name / preview / unread_count` consumer contract

#### Scenario: Richer preview metadata is not stably available
- **WHEN** the macOS Accessibility tree cannot provide optional fields such as sender hints for a session item
- **THEN** the worker still emits the minimal preview-compatible session snapshot instead of expanding scope to right-side full-message capture

### Requirement: Desktop runtime SHALL expose explicit mac listener readiness and permission states without changing the local API surface
The system SHALL keep the current local runtime surface centered on `/healthz`, `/api/runtime`, `/api/sessions`, and the existing worker event stream, while exposing explicit worker states for macOS listener readiness, permission failures, and reconnect progress.

#### Scenario: WeChat is not running or no readable main window is available
- **WHEN** the worker cannot find a usable WeChat main window on macOS
- **THEN** it enters a waiting or reconnecting status such as `waiting_wechat`, `window_lost`, or `reconnecting`, and the backend remains alive for the existing local API consumers

#### Scenario: Accessibility permission is missing
- **WHEN** the worker detects that the current process cannot read the WeChat Accessibility tree
- **THEN** it reports a machine-readable permission-related worker state and detail instead of crashing or silently returning empty snapshots

#### Scenario: Frontend reads runtime and sessions through the shipped local API
- **WHEN** the desktop shell requests `/healthz`, `/api/runtime`, or `/api/sessions`
- **THEN** it continues to use the same local endpoints and receives listener/runtime data that preserves `all_sessions + preview_only` semantics

### Requirement: Desktop listener worker SHALL pause and recover around popup, menu, sheet, and window-loss conditions
The worker SHALL treat popup-style UI interruptions and transient window loss as recoverable runtime states on macOS. It SHALL avoid treating one unstable Accessibility read as a permanent failure for the whole runtime.

#### Scenario: Popup, menu, sheet, or dialog is visible over WeChat
- **WHEN** the macOS window or Accessibility inspection detects a popup-like UI state that makes the tree unreliable
- **THEN** the worker pauses or skips polling with an explicit status and resumes normal reading after the interruption clears

#### Scenario: WeChat window disappears and later returns
- **WHEN** the worker loses the current WeChat main window and WeChat becomes readable again later
- **THEN** it transitions through a controlled reconnect flow and resumes emitting session-preview updates without requiring a manual backend restart
