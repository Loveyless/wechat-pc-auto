export interface ValidationResult {
  valid: boolean;
  errors: string[];
}

export function validateConfigSchema(obj: unknown): ValidationResult {
  const errors: string[] = [];
  if (typeof obj !== "object" || obj === null || Array.isArray(obj)) {
    return { valid: false, errors: ["配置必须是一个 JSON 对象"] };
  }

  const cfg = obj as Record<string, unknown>;
  const listen = cfg.listen as Record<string, unknown> | undefined;
  if (listen) {
    if (listen.mode !== undefined && listen.mode !== "session") {
      errors.push(`listen.mode 只允许 "session"，当前值: "${listen.mode}"`);
    }
    if (listen.interval_seconds !== undefined) {
      const v = Number(listen.interval_seconds);
      if (Number.isNaN(v) || v < 0.3) {
        errors.push(`listen.interval_seconds 不能小于 0.3，当前值: ${listen.interval_seconds}`);
      }
    }
    if (listen.dedupe_window_seconds !== undefined) {
      const v = Number(listen.dedupe_window_seconds);
      if (Number.isNaN(v) || v <= 0) {
        errors.push(`listen.dedupe_window_seconds 必须大于 0，当前值: ${listen.dedupe_window_seconds}`);
      }
    }
    if (listen.session_preview_dedupe_window_seconds !== undefined) {
      const v = Number(listen.session_preview_dedupe_window_seconds);
      if (Number.isNaN(v) || v <= 0) {
        errors.push(`listen.session_preview_dedupe_window_seconds 必须大于 0，当前值: ${listen.session_preview_dedupe_window_seconds}`);
      }
    }
    if (listen.cross_source_merge_window_seconds !== undefined) {
      const v = Number(listen.cross_source_merge_window_seconds);
      if (Number.isNaN(v) || v <= 0) {
        errors.push(`listen.cross_source_merge_window_seconds 必须大于 0，当前值: ${listen.cross_source_merge_window_seconds}`);
      }
    }
    if (listen.use_right_panel_details !== undefined && typeof listen.use_right_panel_details !== "boolean") {
      errors.push("listen.use_right_panel_details 必须是布尔值");
    }
  }

  const translate = cfg.translate as Record<string, unknown> | undefined;
  if (translate) {
    if (translate.timeout_seconds !== undefined) {
      const v = Number(translate.timeout_seconds);
      if (Number.isNaN(v) || v < 1.0) {
        errors.push(`translate.timeout_seconds 不能小于 1.0，当前值: ${translate.timeout_seconds}`);
      }
    }
    if (translate.max_concurrency !== undefined) {
      const v = Number(translate.max_concurrency);
      if (!Number.isInteger(v) || v < 1) {
        errors.push(`translate.max_concurrency 必须是大于 0 的整数，当前值: ${translate.max_concurrency}`);
      }
    }
    if (translate.max_requests_per_second !== undefined) {
      const v = Number(translate.max_requests_per_second);
      if (!Number.isInteger(v) || v < 1) {
        errors.push(`translate.max_requests_per_second 必须是大于 0 的整数，当前值: ${translate.max_requests_per_second}`);
      }
    }
  }

  const display = cfg.display as Record<string, unknown> | undefined;
  if (display) {
    if (display.width !== undefined) {
      const v = Number(display.width);
      if (Number.isNaN(v) || v < 200 || v > 1200) {
        errors.push(`display.width 须在 200–1200 之间，当前值: ${display.width}`);
      }
    }
    if (display.side !== undefined && display.side !== "left" && display.side !== "right") {
      errors.push(`display.side 只允许 "left" 或 "right"，当前值: "${display.side}"`);
    }
    if (display.on_translate_fail !== undefined && display.on_translate_fail !== "show_cn_with_reason" && display.on_translate_fail !== "hide") {
      errors.push(`display.on_translate_fail 只允许 "show_cn_with_reason" 或 "hide"，当前值: "${display.on_translate_fail}"`);
    }
  }

  return { valid: errors.length === 0, errors };
}
