## ADDED Requirements

### Requirement: System monitors all left-sidebar sessions across group and private chats
The system SHALL monitor left-sidebar session previews across both group chats and private chats instead of requiring a manually curated multi-target list for the primary runtime path.

#### Scenario: Group or private chat preview changes
- **WHEN** a group chat or private chat preview changes in the left session list
- **THEN** the backend records the update in the unified desktop event flow

### Requirement: System distinguishes preview-level events from full-message events
The system SHALL model preview-derived updates explicitly and SHALL NOT represent them as guaranteed full-message-body captures in Phase 1.

#### Scenario: Preview text is truncated by WeChat
- **WHEN** the left session list provides only a truncated preview
- **THEN** the backend marks the event as preview-derived rather than claiming complete message fidelity

### Requirement: Session identity remains stable for grouped frontend rendering
The system SHALL maintain stable session identity and ordering data so the frontend can group messages by session and switch the active message stream by session selection.

#### Scenario: User selects a session in the frontend
- **WHEN** the frontend user clicks a session item
- **THEN** the frontend can request or render the matching grouped message stream using the backend session identity
