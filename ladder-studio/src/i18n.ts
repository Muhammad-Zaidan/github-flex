export type Lang = 'id' | 'en';
export type Text = { id: string; en: string };
export const tx = (lang: Lang, t: Text) => t[lang];
