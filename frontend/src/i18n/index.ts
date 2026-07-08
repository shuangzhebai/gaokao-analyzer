import zh from './zh.json';
import en from './en.json';

export type Lang = 'zh' | 'en';
export type TranslationKey = keyof typeof zh;

const messages: Record<Lang, Record<string, string>> = { zh, en };

export function getMessages(lang: Lang): Record<string, string> {
  return messages[lang] || messages.zh;
}

export function t(lang: Lang, key: string, params?: Record<string, string | number>): string {
  const msg = getMessages(lang)[key];
  if (!msg) return key;
  if (!params) return msg;
  return msg.replace(/\{(\w+)\}/g, (_, k) => String(params[k] ?? `{${k}}`));
}
