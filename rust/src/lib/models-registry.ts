/**
 * models.dev API 集成
 * 动态获取 AI 渠道和模型列表
 */

const MODELS_API_URL = "https://models.dev/api.json";
const CACHE_KEY = "models_dev_cache";
const CACHE_TTL_MS = 24 * 60 * 60 * 1000; // 24 小时

export interface ModelInfo {
  id: string;
  name: string;
  family?: string;
  reasoning?: boolean;
  tool_call?: boolean;
  cost?: {
    input: number;
    output: number;
  };
  limit?: {
    context: number;
    output: number;
  };
}

export interface ProviderInfo {
  id: string;
  name: string;
  api: string;
  doc?: string;
  models: ModelInfo[];
}

interface RawProviderData {
  id: string;
  name: string;
  api: string;
  doc?: string;
  models: Record<string, RawModelData>;
}

interface RawModelData {
  id: string;
  name: string;
  family?: string;
  reasoning?: boolean;
  tool_call?: boolean;
  modalities?: {
    input?: string[];
    output?: string[];
  };
  cost?: {
    input: number;
    output: number;
  };
  limit?: {
    context: number;
    output: number;
  };
}

interface CacheData {
  timestamp: number;
  providers: ProviderInfo[];
}

/**
 * 过滤只支持 text → text 的模型（翻译场景）
 */
function filterTextModels(models: Record<string, RawModelData>): ModelInfo[] {
  return Object.values(models)
    .filter((m) => {
      const input = m.modalities?.input ?? ["text"];
      const output = m.modalities?.output ?? ["text"];
      return input.includes("text") && output.includes("text");
    })
    .map((m) => ({
      id: m.id,
      name: m.name,
      family: m.family,
      reasoning: m.reasoning,
      tool_call: m.tool_call,
      cost: m.cost,
      limit: m.limit,
    }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

/**
 * 从 API 获取原始数据
 */
async function fetchFromApi(): Promise<ProviderInfo[]> {
  const resp = await fetch(MODELS_API_URL, {
    headers: { Accept: "application/json" },
  });
  if (!resp.ok) {
    throw new Error(`Failed to fetch models: ${resp.status}`);
  }
  const data = (await resp.json()) as Record<string, RawProviderData>;

  // 转换并过滤
  const providers: ProviderInfo[] = Object.values(data)
    .map((p) => ({
      id: p.id,
      name: p.name,
      api: p.api,
      doc: p.doc,
      models: filterTextModels(p.models),
    }))
    .filter((p) => p.models.length > 0) // 只保留有可用模型的渠道
    .sort((a, b) => a.name.localeCompare(b.name));

  return providers;
}

/**
 * 从缓存读取
 */
function readCache(): ProviderInfo[] | null {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (!raw) return null;

    const cache = JSON.parse(raw) as CacheData;
    if (Date.now() - cache.timestamp > CACHE_TTL_MS) {
      localStorage.removeItem(CACHE_KEY);
      return null;
    }
    return cache.providers;
  } catch {
    return null;
  }
}

/**
 * 写入缓存
 */
function writeCache(providers: ProviderInfo[]): void {
  try {
    const cache: CacheData = {
      timestamp: Date.now(),
      providers,
    };
    localStorage.setItem(CACHE_KEY, JSON.stringify(cache));
  } catch {
    // 忽略缓存写入失败
  }
}

/**
 * 获取所有可用的 AI 渠道和模型
 * 优先使用缓存，缓存过期或不存在时从 API 获取
 */
export async function fetchProviders(): Promise<ProviderInfo[]> {
  // 尝试从缓存读取
  const cached = readCache();
  if (cached) {
    return cached;
  }

  // 从 API 获取
  const providers = await fetchFromApi();
  writeCache(providers);
  return providers;
}

/**
 * 强制刷新缓存
 */
export async function refreshProviders(): Promise<ProviderInfo[]> {
  localStorage.removeItem(CACHE_KEY);
  return fetchProviders();
}

/**
 * 获取指定渠道的模型列表
 */
export function getModelsForProvider(
  providers: ProviderInfo[],
  providerId: string
): ModelInfo[] {
  const provider = providers.find((p) => p.id === providerId);
  return provider?.models ?? [];
}

/**
 * 获取指定渠道的 API 地址
 */
export function getApiUrlForProvider(
  providers: ProviderInfo[],
  providerId: string
): string | undefined {
  const provider = providers.find((p) => p.id === providerId);
  return provider?.api;
}

/**
 * 内置的热门渠道列表（用于 API 请求失败时的降级）
 */
export const BUILTIN_PROVIDERS: ProviderInfo[] = [
  {
    id: "openai",
    name: "OpenAI",
    api: "https://api.openai.com/v1",
    models: [
      { id: "gpt-4o", name: "GPT-4o" },
      { id: "gpt-4o-mini", name: "GPT-4o Mini" },
      { id: "gpt-4-turbo", name: "GPT-4 Turbo" },
    ],
  },
  {
    id: "anthropic",
    name: "Anthropic",
    api: "https://api.anthropic.com/v1",
    models: [
      { id: "claude-3-5-sonnet-20241022", name: "Claude 3.5 Sonnet" },
      { id: "claude-3-5-haiku-20241022", name: "Claude 3.5 Haiku" },
    ],
  },
  {
    id: "deepseek",
    name: "DeepSeek",
    api: "https://api.deepseek.com",
    models: [
      { id: "deepseek-chat", name: "DeepSeek Chat" },
      { id: "deepseek-reasoner", name: "DeepSeek Reasoner" },
    ],
  },
  {
    id: "groq",
    name: "Groq",
    api: "https://api.groq.com/openai/v1",
    models: [
      { id: "llama-3.3-70b-versatile", name: "Llama 3.3 70B" },
      { id: "mixtral-8x7b-32768", name: "Mixtral 8x7B" },
    ],
  },
  {
    id: "moonshot",
    name: "Moonshot",
    api: "https://api.moonshot.cn/v1",
    models: [
      { id: "moonshot-v1-8k", name: "Moonshot V1 8K" },
      { id: "moonshot-v1-32k", name: "Moonshot V1 32K" },
    ],
  },
  {
    id: "openrouter",
    name: "OpenRouter",
    api: "https://openrouter.ai/api/v1",
    models: [
      { id: "openai/gpt-4o", name: "GPT-4o (via OpenRouter)" },
      { id: "anthropic/claude-3.5-sonnet", name: "Claude 3.5 Sonnet (via OpenRouter)" },
    ],
  },
];
