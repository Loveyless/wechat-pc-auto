import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Search,
  User,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  MessageSquare,
  Users,
  Database,
  Loader2,
  Trash2,
  AlertTriangle,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { convertFileSrc } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import * as api from "@/lib/tauri-api";
import { useToastStore } from "@/stores/toastStore";
import type { StoredMessage } from "@/lib/types";

interface ChatSummary {
  chat_name: string;
  message_count: number;
  last_message_at: string;
}

interface DbStats {
  total_messages: number;
  total_chats: number;
  earliest_message: string;
  latest_message: string;
}

const PAGE_SIZE = 50;

const AVATAR_COLORS = [
  "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
  "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  "bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300",
  "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300",
  "bg-cyan-100 text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-300",
];

function getInitial(name: string): string {
  if (!name) return "?";
  const t = name.trim();
  return /[\u4e00-\u9fff]/.test(t) ? t.slice(-1) : t[0].toUpperCase();
}

function avatarColor(name: string): string {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = name.charCodeAt(i) + ((h << 5) - h);
  return AVATAR_COLORS[Math.abs(h) % AVATAR_COLORS.length];
}

export function MessageHistory() {
  const showToast = useToastStore((s) => s.showToast);
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [stats, setStats] = useState<DbStats | null>(null);
  const [selectedChat, setSelectedChat] = useState<string | null>(null);
  const [messages, setMessages] = useState<StoredMessage[]>([]);
  const [keyword, setKeyword] = useState("");
  const [senderFilter, setSenderFilter] = useState("");
  const [chatSearch, setChatSearch] = useState("");
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(false);
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [clearing, setClearing] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const loadChats = useCallback(async () => {
    try {
      const resp = (await api.dbGetChats()) as unknown as Record<string, unknown>;
      const data = resp.data as ChatSummary[] | undefined;
      if (data) setChats(data);
    } catch {
      /* ignore */
    }
  }, []);

  const loadStats = useCallback(async () => {
    try {
      const resp = (await api.dbGetStats()) as unknown as Record<string, unknown>;
      const data = resp.data as DbStats | undefined;
      if (data) setStats(data);
    } catch {
      /* ignore */
    }
  }, []);

  const loadMessages = useCallback(
    async (chatName: string | null, kw: string, sender: string, pg: number) => {
      setLoading(true);
      try {
        const resp = (await api.dbQueryMessages({
          chatName: chatName ?? undefined,
          sender: sender || undefined,
          keyword: kw || undefined,
          limit: PAGE_SIZE,
          offset: pg * PAGE_SIZE,
        })) as unknown as Record<string, unknown>;
        const data = resp.data as StoredMessage[] | undefined;
        setMessages(data ?? []);
      } catch (e) {
        showToast(`${e}`, false);
      } finally {
        setLoading(false);
      }
    },
    [showToast],
  );

  useEffect(() => {
    loadChats();
    loadStats();
  }, [loadChats, loadStats]);

  useEffect(() => {
    const unlisten = listen("db-cleared-restart", () => {
      setShowClearConfirm(false);
      setSelectedChat(null);
      setPage(0);
      setKeyword("");
      setSenderFilter("");
      setMessages([]);
      loadChats();
      loadStats();
    });

    return () => {
      unlisten.then((fn) => fn());
    };
  }, [loadChats, loadStats]);

  useEffect(() => {
    const timer = setTimeout(
      () => loadMessages(selectedChat, keyword, senderFilter, page),
      keyword || senderFilter ? 300 : 0,
    );
    return () => clearTimeout(timer);
  }, [selectedChat, keyword, senderFilter, page, loadMessages]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: 0 });
  }, [messages]);

  function handleRefresh() {
    loadChats();
    loadStats();
    loadMessages(selectedChat, keyword, senderFilter, page);
  }

  async function handleClearRestart() {
    setClearing(true);
    try {
      await api.dbClearRestart();
      showToast("数据库已清空，监听已重启", true);
      setShowClearConfirm(false);
      setSelectedChat(null);
      setPage(0);
      setKeyword("");
      setSenderFilter("");
      setMessages([]);
      loadChats();
      loadStats();
    } catch (e) {
      showToast(`清空失败: ${e}`, false);
    } finally {
      setClearing(false);
    }
  }

  const filteredChats = useMemo(() => {
    if (!chatSearch.trim()) return chats;
    const q = chatSearch.toLowerCase();
    return chats.filter((c) => c.chat_name.toLowerCase().includes(q));
  }, [chats, chatSearch]);

  const rangeStart = page * PAGE_SIZE + 1;
  const rangeEnd = page * PAGE_SIZE + messages.length;

  return (
    <div className="flex gap-4 h-[calc(100vh-140px)]">
      {/* ── Left Panel: Chat List ── */}
      <div className="w-[220px] shrink-0 flex flex-col glass-card rounded-2xl shadow-sm overflow-hidden">
        {/* Stats overview */}
        <div className="p-4 space-y-3 border-b border-border/50">
          <div className="flex items-center justify-between">
            <h3 className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
              会话
            </h3>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={handleRefresh}
            >
              <RefreshCw className="w-3 h-3" />
            </Button>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="flex items-center gap-2 px-2.5 py-2 rounded-xl bg-primary/10">
              <MessageSquare className="w-3.5 h-3.5 text-primary shrink-0" />
              <div className="min-w-0">
                <p className="text-sm font-semibold text-foreground leading-none">
                  {stats?.total_messages ?? "—"}
                </p>
                <p className="text-[10px] text-muted-foreground mt-0.5">消息</p>
              </div>
            </div>
            <div className="flex items-center gap-2 px-2.5 py-2 rounded-xl bg-blue-500/10">
              <Users className="w-3.5 h-3.5 text-blue-500 shrink-0" />
              <div className="min-w-0">
                <p className="text-sm font-semibold text-foreground leading-none">
                  {stats?.total_chats ?? "—"}
                </p>
                <p className="text-[10px] text-muted-foreground mt-0.5">会话</p>
              </div>
            </div>
          </div>
        </div>

        {/* Clear DB button */}
        <div className="px-4 pb-3">
          <Button
            variant="ghost"
            size="sm"
            className="w-full h-7 text-[11px] text-destructive hover:text-destructive hover:bg-destructive/10 gap-1.5"
            onClick={() => setShowClearConfirm(true)}
            disabled={!stats || stats.total_messages === 0}
          >
            <Trash2 className="w-3 h-3" />
            清空数据库并重启
          </Button>
        </div>

        {/* Chat search */}
        <div className="px-3 py-2.5 border-b border-border/30">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
            <Input
              placeholder="搜索会话..."
              className="h-8 pl-8 text-xs"
              value={chatSearch}
              onChange={(e) => setChatSearch(e.target.value)}
            />
          </div>
        </div>

        {/* Chat list */}
        <div className="flex-1 overflow-y-auto px-2 py-1.5 space-y-0.5">
          {/* "All" entry */}
          <button
            onClick={() => {
              setSelectedChat(null);
              setPage(0);
            }}
            className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-left text-[13px] transition-all relative ${
              selectedChat === null
                ? "bg-primary/10 text-foreground font-medium"
                : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
            }`}
          >
            {selectedChat === null && (
              <motion.div
                layoutId="chat-active"
                className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full bg-primary"
                transition={{ type: "spring", stiffness: 400, damping: 30 }}
              />
            )}
            <Database className="w-4 h-4 shrink-0" />
            <span className="flex-1 truncate">全部会话</span>
            {stats && (
              <Badge variant="secondary" className="text-[10px] h-5 px-1.5">
                {stats.total_messages}
              </Badge>
            )}
          </button>

          {/* Individual chats */}
          {filteredChats.map((c) => (
            <button
              key={c.chat_name}
              onClick={() => {
                setSelectedChat(c.chat_name);
                setPage(0);
              }}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-left text-[13px] transition-all relative ${
                selectedChat === c.chat_name
                  ? "bg-primary/10 text-foreground font-medium"
                  : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
              }`}
            >
              {selectedChat === c.chat_name && (
                <motion.div
                  layoutId="chat-active"
                  className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full bg-primary"
                  transition={{ type: "spring", stiffness: 400, damping: 30 }}
                />
              )}
              <div
                className={`w-7 h-7 rounded-lg flex items-center justify-center text-[11px] font-semibold shrink-0 ${avatarColor(c.chat_name)}`}
              >
                {getInitial(c.chat_name)}
              </div>
              <div className="flex-1 min-w-0">
                <p className="truncate text-[13px]">{c.chat_name}</p>
                <p className="text-[10px] text-muted-foreground truncate">
                  {c.last_message_at}
                </p>
              </div>
              <Badge variant="secondary" className="text-[10px] h-5 px-1.5 shrink-0">
                {c.message_count}
              </Badge>
            </button>
          ))}

          {/* Chat list empty states */}
          {filteredChats.length === 0 && chats.length > 0 && (
            <div className="text-center py-6 text-xs text-muted-foreground">
              未找到匹配的会话
            </div>
          )}
          {chats.length === 0 && (
            <div className="flex flex-col items-center py-10 gap-2">
              <Database className="w-8 h-8 text-muted-foreground/20" />
              <p className="text-xs text-muted-foreground">暂无会话</p>
            </div>
          )}
        </div>
      </div>

      {/* ── Right Panel: Messages ── */}
      <div className="flex-1 flex flex-col glass-card rounded-2xl shadow-sm overflow-hidden min-w-0">
        {/* Header with search */}
        <div className="shrink-0 px-5 py-3.5 border-b border-border/50 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <h3 className="text-sm font-semibold text-foreground">
                {selectedChat ?? "全部消息"}
              </h3>
              {loading && (
                <Loader2 className="w-3.5 h-3.5 text-muted-foreground animate-spin" />
              )}
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={handleRefresh}
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </Button>
          </div>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
              <Input
                placeholder="搜索消息内容..."
                className="h-8 pl-8 text-xs"
                value={keyword}
                onChange={(e) => {
                  setKeyword(e.target.value);
                  setPage(0);
                }}
              />
            </div>
            <div className="relative w-36">
              <User className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
              <Input
                placeholder="发送人..."
                className="h-8 pl-8 text-xs"
                value={senderFilter}
                onChange={(e) => {
                  setSenderFilter(e.target.value);
                  setPage(0);
                }}
              />
            </div>
          </div>
        </div>

        {/* Message list */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          <AnimatePresence mode="wait">
            {loading && messages.length === 0 ? (
              <motion.div
                key="loading"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-col items-center justify-center py-20 gap-3"
              >
                <Loader2 className="w-6 h-6 text-muted-foreground animate-spin" />
                <p className="text-sm text-muted-foreground">加载中...</p>
              </motion.div>
            ) : !loading && messages.length === 0 ? (
              <motion.div
                key="empty"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                className="flex flex-col items-center justify-center py-20 gap-3"
              >
                {keyword || senderFilter ? (
                  <>
                    <Search className="w-10 h-10 text-muted-foreground/20" />
                    <p className="text-sm text-muted-foreground">
                      未找到匹配的消息
                    </p>
                    <p className="text-xs text-muted-foreground/60">
                      尝试调整搜索关键词或发送人筛选
                    </p>
                  </>
                ) : (
                  <>
                    <Database className="w-10 h-10 text-muted-foreground/20" />
                    <p className="text-sm text-muted-foreground">暂无消息记录</p>
                    <p className="text-xs text-muted-foreground/60">
                      开启实时浮窗后，消息将自动存储到此处
                    </p>
                  </>
                )}
              </motion.div>
            ) : (
              <motion.div
                key="messages"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="divide-y divide-border/30"
              >
                {messages.map((msg) => (
                  <div
                    key={msg.id}
                    className="flex items-start gap-3 px-5 py-3 hover:bg-accent/30 transition-colors"
                  >
                    <div
                      className={`w-8 h-8 rounded-full flex items-center justify-center text-[11px] font-semibold shrink-0 mt-0.5 ${avatarColor(msg.sender || msg.chat_name)}`}
                    >
                      {getInitial(msg.sender || msg.chat_name)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-baseline gap-2">
                        <span className="text-[13px] font-medium text-foreground truncate">
                          {msg.sender || msg.chat_name}
                        </span>
                        {selectedChat === null && (
                          <Badge
                            variant="outline"
                            className="text-[10px] font-normal h-4 px-1.5 shrink-0"
                          >
                            {msg.chat_name}
                          </Badge>
                        )}
                        <span className="text-[10px] text-muted-foreground font-mono ml-auto shrink-0">
                          {msg.detected_at}
                        </span>
                      </div>
                      {msg.image_path ? (
                        <div className="mt-1 flex justify-start">
                          <div className="relative w-full max-w-[220px] min-w-[180px] rounded-[30px] border border-white/10 bg-gradient-to-b from-slate-900/80 to-slate-800/60 p-2 shadow-lg shadow-slate-900/30 dark:from-white/10 dark:to-white/5 dark:border-white/5">
                            <div className="absolute left-1/2 top-2 h-1.5 w-12 -translate-x-1/2 rounded-full bg-white/20" />
                            <div className="overflow-hidden rounded-[24px] bg-black/90">
                              <div className="aspect-[9/19.5] min-h-[360px] w-full">
                                <img
                                  src={convertFileSrc(msg.image_path)}
                                  alt="chat image"
                                  className="h-full w-full object-cover"
                                  loading="lazy"
                                />
                              </div>
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div className="mt-0.5 space-y-1">
                          <p className="text-xs text-muted-foreground leading-relaxed break-all">
                            {msg.content}
                          </p>
                          {msg.content_en && msg.content_en !== msg.content && (
                            <p className="text-xs text-sky-700/70 dark:text-sky-300/60 leading-relaxed break-all">
                              {msg.content_en}
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Pagination */}
        <div className="shrink-0 flex items-center justify-between px-5 py-2.5 border-t border-border/50 bg-muted/10">
          <span className="text-[11px] text-muted-foreground">
            {messages.length > 0
              ? `第 ${page + 1} 页 · 第 ${rangeStart}–${rangeEnd} 条`
              : `第 ${page + 1} 页`}
            {messages.length === PAGE_SIZE && " · 更多"}
          </span>
          <div className="flex gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              disabled={page === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
            >
              <ChevronLeft className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              disabled={messages.length < PAGE_SIZE}
              onClick={() => setPage((p) => p + 1)}
            >
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </div>

      <AnimatePresence>
        {showClearConfirm ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
            onClick={() => !clearing && setShowClearConfirm(false)}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ type: "spring", stiffness: 400, damping: 30 }}
              className="glass-card w-[360px] space-y-4 rounded-2xl p-6 shadow-xl"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-destructive/10">
                  <AlertTriangle className="h-5 w-5 text-destructive" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-foreground">清空数据库</h3>
                  <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                    此操作将删除所有 {stats?.total_messages ?? 0} 条消息记录并重启监听服务，数据不可恢复。
                  </p>
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 text-xs"
                  onClick={() => setShowClearConfirm(false)}
                  disabled={clearing}
                >
                  取消
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  className="h-8 gap-1.5 text-xs"
                  onClick={handleClearRestart}
                  disabled={clearing}
                >
                  {clearing ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Trash2 className="h-3 w-3" />
                  )}
                  {clearing ? "清空中..." : "确认清空"}
                </Button>
              </div>
            </motion.div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
