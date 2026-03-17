import { describe, expect, it } from "vitest"

import {
  resolveDesktopSettingsProviderSections,
  resolveDesktopSettingsTranslateSections,
} from "@/components/shell/settings-workspace"

describe("settings workspace translate sections", () => {
  it("renders deeplx as the only deeplx branch", () => {
    expect(resolveDesktopSettingsTranslateSections("deeplx")).toEqual({
      showDeeplxFields: true,
      showOpenAICompatibleFields: false,
      showPassthroughNotice: false,
    })
  })

  it("renders openai_compatible and passthrough as exclusive branches", () => {
    expect(resolveDesktopSettingsTranslateSections("openai_compatible")).toEqual({
      showDeeplxFields: false,
      showOpenAICompatibleFields: true,
      showPassthroughNotice: false,
    })
    expect(resolveDesktopSettingsTranslateSections("passthrough")).toEqual({
      showDeeplxFields: false,
      showOpenAICompatibleFields: false,
      showPassthroughNotice: true,
    })
  })
})

describe("settings workspace provider sections", () => {
  it("renders windows_system as notice-only branch", () => {
    expect(resolveDesktopSettingsProviderSections("windows_system")).toEqual({
      showWindowsSystemNotice: true,
      showDoubaoFields: false,
      showTencentFields: false,
    })
  })

  it("renders doubao and tencent_cloud as exclusive provider forms", () => {
    expect(resolveDesktopSettingsProviderSections("doubao")).toEqual({
      showWindowsSystemNotice: false,
      showDoubaoFields: true,
      showTencentFields: false,
    })
    expect(resolveDesktopSettingsProviderSections("tencent_cloud")).toEqual({
      showWindowsSystemNotice: false,
      showDoubaoFields: false,
      showTencentFields: true,
    })
  })
})
