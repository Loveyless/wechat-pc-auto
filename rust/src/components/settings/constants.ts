export const SOURCE_LANGS = [
  { value: "auto", label: "auto (自动检测)" },
  { value: "ZH", label: "ZH (中文)" },
  { value: "EN", label: "EN (英语)" },
  { value: "JA", label: "JA (日语)" },
  { value: "KO", label: "KO (韩语)" },
  { value: "DE", label: "DE (德语)" },
  { value: "FR", label: "FR (法语)" },
  { value: "ES", label: "ES (西班牙语)" },
  { value: "RU", label: "RU (俄语)" },
];

export const TARGET_LANGS = SOURCE_LANGS.filter((l) => l.value !== "auto");
