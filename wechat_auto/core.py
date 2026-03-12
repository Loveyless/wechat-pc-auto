from .window import WeChatWindow


class WxAuto:
    """纯监听分支仅保留微信主窗口加载与只读会话查询能力。"""

    def __init__(self):
        self._window_manager = WeChatWindow()
        self.window = None

    def load_wechat(self) -> bool:
        """加载微信窗口"""
        success = self._window_manager.load()
        if success:
            self.window = self._window_manager.get_window()
        else:
            self.window = None
        return success

    def get_current_sessions(self) -> list:
        """获取当前会话列表"""
        return self._window_manager.get_current_sessions()
