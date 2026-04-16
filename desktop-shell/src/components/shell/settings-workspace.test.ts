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
  it("renders macos_system as notice-only branch", () => {
    expect(resolveDesktopSettingsProviderSections("macos_system")).toEqual({
      showMacOSSystemNotice: true,
      showDoubaoFields: false,
      showLessTtsFields: false,
      showTencentFields: false,
    })
  })

  it("renders doubao, less_tts, and tencent_cloud as exclusive provider forms", () => {
    expect(resolveDesktopSettingsProviderSections("doubao")).toEqual({
      showMacOSSystemNotice: false,
      showDoubaoFields: true,
      showLessTtsFields: false,
      showTencentFields: false,
    })
    expect(resolveDesktopSettingsProviderSections("less_tts")).toEqual({
      showMacOSSystemNotice: false,
      showDoubaoFields: false,
      showLessTtsFields: true,
      showTencentFields: false,
    })
    expect(resolveDesktopSettingsProviderSections("tencent_cloud")).toEqual({
      showMacOSSystemNotice: false,
      showDoubaoFields: false,
      showLessTtsFields: false,
      showTencentFields: true,
    })
  })
})
