import { createContext, useState, useCallback, useEffect, type ReactNode } from 'react';
import type { FC } from 'react';
import { t as translate, type Lang } from '../i18n';

interface I18nContextType {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
}

export const I18nContext = createContext<I18nContextType>({
  lang: 'zh', setLang: () => {}, t: (k) => k,
});

export const I18nProvider: FC<{ children: ReactNode }> = ({ children }) => {
  const [lang, setLangState] = useState<Lang>(() => {
    const saved = localStorage.getItem('lang') as Lang | null;
    if (saved) return saved;
    return navigator.language.startsWith('en') ? 'en' : 'zh';
  });

  const setLang = useCallback((l: Lang) => {
    localStorage.setItem('lang', l);
    setLangState(l);
    document.documentElement.lang = l;
  }, []);

  const t = useCallback((key: string, params?: Record<string, string | number>) => {
    return translate(lang, key, params);
  }, [lang]);

  useEffect(() => { document.documentElement.lang = lang; }, [lang]);

  return (
    <I18nContext.Provider value={{ lang, setLang, t }}>
      {children}
    </I18nContext.Provider>
  );
};
