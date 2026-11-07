import { useState } from "react";
import { FileText, Image, Paperclip, Trash2 } from "lucide-react";
import { uid } from "../../app/store";
import { Badge, Button, Field, Notice } from "../../components/ui";
import type { Evidence } from "../../types";

export function EvidencePicker({
  items,
  onChange,
}: {
  items: Evidence[];
  onChange: (items: Evidence[]) => void;
}) {
  const [note, setNote] = useState("");
  const [timestamp, setTimestamp] = useState("");
  const add = (kind: Evidence["kind"]) => {
    const text =
      kind === "text_note"
        ? note.trim()
        : kind === "screenshot"
          ? "Nhiều tin nhắn trong nhóm; tên người gửi bị che. Danh tính và ngữ cảnh chưa được kiểm tra."
          : "Tài liệu PDF minh họa: ghi chú về một buổi làm bài nhóm. Đây là placeholder, không phải tệp đã tải lên.";
    if (!text) return;
    onChange([
      ...items,
      {
        id: uid("EVIDENCE"),
        kind,
        origin: kind === "text_note" ? "user_entered" : "mock_fixture",
        ...(kind === "screenshot"
          ? { assetPath: "/fixtures/messenger_07.svg" }
          : {}),
        shownTimestamp:
          timestamp ||
          (kind === "screenshot" ? "2026-10-16T19:55:00+07:00" : ""),
        originalText: text,
        extractedText: text,
        reviewStatus: "unreviewed",
        limitations: [
          "Chưa xác minh nguồn và ngữ cảnh đầy đủ",
          ...(kind !== "text_note" ? ["Nội dung hoàn toàn giả lập"] : []),
        ],
      },
    ]);
    setNote("");
  };
  return (
    <div className="stack evidence-picker">
      <Notice>
        Chỉ dùng dữ liệu giả trong bản demo. Nút đính kèm thêm tệp mẫu, không mở
        hay tải tệp riêng tư của bạn.
      </Notice>
      <div className="actions">
        <Button
          variant="secondary"
          type="button"
          onClick={() => add("screenshot")}
        >
          <Image size={18} />
          Ảnh chụp mẫu
        </Button>
        <Button
          variant="secondary"
          type="button"
          onClick={() => add("pdf_placeholder")}
        >
          <FileText size={18} />
          PDF mẫu
        </Button>
      </div>
      <Field label="Ghi chú hoặc đoạn tin nhắn mẫu" id="evidence-note">
        <textarea
          id="evidence-note"
          rows={3}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Chép nội dung minh họa bạn muốn giữ lại…"
        />
      </Field>
      <Field
        label="Mốc thời gian hiển thị trong nội dung (nếu có)"
        value={timestamp}
        onChange={(e) => setTimestamp(e.target.value)}
        placeholder="Ví dụ: khoảng chiều thứ Hai; chưa rõ"
      />
      <Button
        type="button"
        variant="secondary"
        disabled={!note.trim()}
        onClick={() => add("text_note")}
      >
        <Paperclip size={18} />
        Thêm ghi chú
      </Button>
      {items.length > 0 && (
        <ul className="evidence-attachments">
          {items.map((item) => (
            <li key={item.id}>
              <FileText size={20} />
              <div>
                <strong>
                  {item.kind === "screenshot"
                    ? "Ảnh chụp mẫu"
                    : item.kind === "pdf_placeholder"
                      ? "PDF mẫu"
                      : "Ghi chú"}
                </strong>
                <p>{item.originalText}</p>
                <Badge tone="amber">Chưa kiểm tra</Badge>
              </div>
              <Button
                variant="ghost"
                type="button"
                aria-label={`Bỏ ${item.id}`}
                onClick={() => onChange(items.filter((e) => e.id !== item.id))}
              >
                <Trash2 size={18} />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
