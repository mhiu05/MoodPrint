/**
 * Client-only, non-blocking advisory (I-06): does a draft look like it shares contact
 * details? Never sent anywhere; the user can always choose to send anyway.
 */
const EMAIL = /[^\s@]+@[^\s@]+\.[a-z]{2,}/i;
const URL = /\b(?:https?:\/\/|www\.)\S+|\b[a-z0-9-]+\.(?:com|vn|net|org|io|me|app|link)\b/i;
// Vietnamese numbers: +84 or 0 followed by 9-10 digits, allowing space, dot or dash groups.
const PHONE = /(?:\+84|\b0)\d{9,10}\b/;

export function looksLikeContact(text: string) {
  const compact = text.replace(/(\d)[ .-](?=\d)/g, "$1");
  return EMAIL.test(text) || URL.test(text) || PHONE.test(compact);
}
