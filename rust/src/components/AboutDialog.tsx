import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import {
  Info,
  Github,
  ExternalLink,
  Download,
  CheckCircle2,
  Loader2,
  AlertCircle,
  X,
} from "lucide-react";
import { getVersion } from "@tauri-apps/api/app";
import { openUrl } from "@tauri-apps/plugin-opener";
import { motion, AnimatePresence } from "framer-motion";

const GITHUB_REPO = "congwa/wechat-translate";
const GITHUB_URL = `https://github.com/${GITHUB_REPO}`;
const RELEASES_URL = `${GITHUB_URL}/releases`;
const RELEASES_API = `https://api.github.com/repos/${GITHUB_REPO}/releases/latest`;

interface ReleaseInfo {
  tag_name: string;
  name: string;
  html_url: string;
  published_at: string;
  body: string;
}

type UpdateStatus = "idle" | "checking" | "up-to-date" | "update-available" | "error";

function compareVersions(current: string, latest: string): number {
  const normalize = (v: string) => v.replace(/^v/, "").split(".").map(Number);
  const [a, b] = [normalize(current), normalize(latest)];
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    const diff = (b[i] || 0) - (a[i] || 0);
    if (diff !== 0) return diff;
  }
  return 0;
}

export function AboutDialog() {
  const [isOpen, setIsOpen] = useState(false);
  const [version, setVersion] = useState<string>("");
  const [updateStatus, setUpdateStatus] = useState<UpdateStatus>("idle");
  const [latestRelease, setLatestRelease] = useState<ReleaseInfo | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    if (isOpen) {
      getVersion().then(setVersion).catch(() => setVersion("unknown"));
    }
  }, [isOpen]);

  async function checkForUpdates() {
    setUpdateStatus("checking");
    setError("");
    setLatestRelease(null);

    try {
      const response = await fetch(RELEASES_API, {
        headers: { Accept: "application/vnd.github.v3+json" },
      });

      if (!response.ok) {
        throw new Error(`GitHub API 返回 ${response.status}`);
      }

      const release: ReleaseInfo = await response.json();
      setLatestRelease(release);

      const latestVersion = release.tag_name.replace(/^v/, "");
      const currentVersion = version.replace(/^v/, "");

      if (compareVersions(currentVersion, latestVersion) > 0) {
        setUpdateStatus("update-available");
      } else {
        setUpdateStatus("up-to-date");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "检查更新失败");
      setUpdateStatus("error");
    }
  }

  async function handleOpenLink(url: string) {
    try {
      await openUrl(url);
    } catch {
      window.open(url, "_blank");
    }
  }

  return (
    <>
      <button
        onClick={() => setIsOpen(true)}
        className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-[13px] font-medium transition-all duration-150 hover:text-white/90"
        style={{ color: "inherit" }}
      >
        <Info className="w-[18px] h-[18px] opacity-85" />
        <span className="flex-1 text-left">关于</span>
      </button>

      <AnimatePresence>
        {isOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/50 z-50"
              onClick={() => setIsOpen(false)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-md bg-background rounded-2xl shadow-2xl border"
            >
              <div className="flex items-center justify-between p-4 border-b">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                    <img src="/icon.png" alt="Logo" className="w-6 h-6" onError={(e) => {
                      (e.target as HTMLImageElement).style.display = "none";
                    }} />
                  </div>
                  <div>
                    <h2 className="text-lg font-semibold">WeChat Translate</h2>
                    <p className="text-xs text-muted-foreground">微信翻译助手</p>
                  </div>
                </div>
                <button
                  onClick={() => setIsOpen(false)}
                  className="p-2 rounded-lg hover:bg-muted transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="p-4 space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">当前版本</span>
                  <span className="text-sm font-mono font-medium bg-muted px-2 py-0.5 rounded">v{version}</span>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">技术栈</span>
                  <span className="text-sm">macOS · Rust + Tauri</span>
                </div>

                <div className="border-t pt-4 space-y-2">
                  <Button
                    variant="outline"
                    className="w-full justify-start gap-2"
                    onClick={() => handleOpenLink(GITHUB_URL)}
                  >
                    <Github className="w-4 h-4" />
                    GitHub 仓库
                    <ExternalLink className="w-3 h-3 ml-auto opacity-50" />
                  </Button>

                  <Button
                    variant="outline"
                    className="w-full justify-start gap-2"
                    onClick={() => handleOpenLink(RELEASES_URL)}
                  >
                    <Download className="w-4 h-4" />
                    下载页面
                    <ExternalLink className="w-3 h-3 ml-auto opacity-50" />
                  </Button>
                </div>

                <div className="border-t pt-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">检查更新</span>
                    {updateStatus === "up-to-date" && (
                      <span className="text-xs text-emerald-600 flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3" />
                        已是最新版本
                      </span>
                    )}
                    {updateStatus === "update-available" && latestRelease && (
                      <span className="text-xs text-amber-600 flex items-center gap-1">
                        <Download className="w-3 h-3" />
                        有新版本: {latestRelease.tag_name}
                      </span>
                    )}
                    {updateStatus === "error" && (
                      <span className="text-xs text-red-600 flex items-center gap-1">
                        <AlertCircle className="w-3 h-3" />
                        检查失败
                      </span>
                    )}
                  </div>

                  {updateStatus === "update-available" && latestRelease && (
                    <div className="rounded-lg border border-amber-200 bg-amber-50/50 dark:bg-amber-900/10 dark:border-amber-800/30 p-3 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">{latestRelease.name || latestRelease.tag_name}</span>
                        <span className="text-xs text-muted-foreground">
                          {new Date(latestRelease.published_at).toLocaleDateString()}
                        </span>
                      </div>
                      {latestRelease.body && (
                        <p className="text-xs text-muted-foreground line-clamp-3">
                          {latestRelease.body.slice(0, 200)}...
                        </p>
                      )}
                      <Button
                        size="sm"
                        className="w-full"
                        onClick={() => handleOpenLink(latestRelease.html_url)}
                      >
                        <Download className="w-3 h-3 mr-2" />
                        前往下载
                      </Button>
                    </div>
                  )}

                  {error && (
                    <p className="text-xs text-red-600">{error}</p>
                  )}

                  <Button
                    variant="outline"
                    className="w-full"
                    onClick={checkForUpdates}
                    disabled={updateStatus === "checking"}
                  >
                    {updateStatus === "checking" ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        检查中...
                      </>
                    ) : (
                      <>
                        <Download className="w-4 h-4 mr-2" />
                        检查更新
                      </>
                    )}
                  </Button>
                </div>

                <div className="border-t pt-4 text-center">
                  <p className="text-xs text-muted-foreground">
                    Made with ❤️ by{" "}
                    <button
                      className="text-primary hover:underline"
                      onClick={() => handleOpenLink("https://github.com/congwa")}
                    >
                      congwa
                    </button>
                    {" & "}
                    <button
                      className="text-primary hover:underline"
                      onClick={() => handleOpenLink("https://github.com/Loveyless")}
                    >
                      Loveyless
                    </button>
                  </p>
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
