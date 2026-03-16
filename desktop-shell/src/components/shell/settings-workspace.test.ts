import { describe, expect, it } from "vitest"

import { resolveDesktopSettingsProviderSections } from "@/components/shell/settings-workspace"

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
