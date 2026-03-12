const ERROR_MAP: [RegExp, string][] = [
  [/AXError|kAXErrorAPIDisabled/i, "辅助功能权限未授权，请在系统设置中开启"],
  [/未检测到微信进程/, "微信未运行，请先启动并登录微信"],
  [/已有监听类任务在运行|already.*running/i, "有其他任务正在运行，请先停止"],
  [/DeepLX|翻译服务|translate.*fail/i, "翻译服务连接失败，请检查地址和 API Key 是否正确"],
  [/无法获取微信窗口/, "无法读取微信窗口，请检查辅助功能权限"],
  [/无法创建 AXUIElement/, "无法访问微信进程，请检查辅助功能权限"],
  [/消息不能为空/, "消息内容不能为空"],
  [/文件不存在/, "指定的文件不存在，请检查路径"],
  [/file_paths 不能为空/, "请至少选择一个文件"],
];

export function humanizeError(raw: string): string {
  for (const [pattern, friendly] of ERROR_MAP) {
    if (pattern.test(raw)) {
      return friendly;
    }
  }
  return raw;
}
