export const formatDate = (value: string) =>
  value ? new Date(value).toLocaleDateString("vi-VN") : "Chưa rõ thời gian";
export const normalize = (value: string) =>
  value
    .toLocaleLowerCase("vi")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d");
export async function copyText(text: string) {
  await navigator.clipboard.writeText(text);
}
export function downloadText(text: string, filename = "safevoice-demo.txt") {
  const url = URL.createObjectURL(
    new Blob([text], { type: "text/plain;charset=utf-8" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
