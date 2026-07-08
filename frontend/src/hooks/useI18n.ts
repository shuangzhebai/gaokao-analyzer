import { useContext } from 'react';
import { I18nContext } from '../contexts/I18nContext';

export function useI18n() {
  return useContext(I18nContext);
}
