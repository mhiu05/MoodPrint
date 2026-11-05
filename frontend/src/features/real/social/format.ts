/** Short Vietnamese relative time for list rows; dates older than a week show dd/mm. */
export function relativeTime(iso: string, now = Date.now()) {
  const then = new Date(iso).getTime();
  const minutes = Math.floor(Math.max(0, now - then) / 60_000);
  if (minutes < 1) return "vừa xong";
  if (minutes < 60) return `${minutes} phút trước`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} giờ trước`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "hôm qua";
  if (days < 7) return `${days} ngày trước`;
  const date = new Date(iso);
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${pad(date.getDate())}/${pad(date.getMonth() + 1)}`;
}

/** Message-list preview: own messages are prefixed so the row reads naturally. */
export function previewLine(text: string | null | undefined, sender?: string | null) {
  if (!text) return "Chưa có tin nhắn. Hãy bắt đầu bằng một lời hỏi thăm.";
  return sender === "self" ? `Bạn: ${text}` : text;
}
