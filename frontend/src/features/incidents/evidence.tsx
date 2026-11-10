import { useEffect, useRef, useState } from "react";
import { FileText, Image, Paperclip, Trash2 } from "lucide-react";
import { uid, useWorkspaceStore } from "../../app/store";
import { getServices } from "../../services/composition";
import type { UploadController } from "../../services/ports";
import { Badge, Button, Field, Notice } from "../../components/ui";
import type { Evidence } from "../../types";

export function EvidencePicker(props: {
  items: Evidence[];
  onChange: (items: Evidence[]) => void;
}) {
  const kind = useWorkspaceStore((state) => state.workspace.kind);
  return kind === "real" ? (
    <RealEvidencePicker {...props} />
  ) : (
    <DemoEvidencePicker {...props} />
  );
}

function RealEvidencePicker({
  items,
  onChange,
}: {
  items: Evidence[];
  onChange: (items: Evidence[]) => void;
}) {
  const [note, setNote] = useState("");
  const [timestamp, setTimestamp] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [jobs, setJobs] = useState<
    Record<
      string,
      {
        name: string;
        progress: number;
        status: "uploading" | "paused" | "error" | "done" | "cancelled";
        error?: string;
      }
    >
  >({});
  const controllers = useRef(new Map<string, UploadController>());
  const input = useRef<HTMLInputElement>(null);
  const current = useRef(items);
  useEffect(() => {
    current.current = items;
  }, [items]);
  const evidence = useWorkspaceStore((state) => state.evidence);
  const available = evidence.filter(
    (item) =>
      !item.caseId &&
      item.origin !== "mock_fixture" &&
      item.uploadStatus === "uploaded" &&
      !items.some((selected) => selected.id === item.id),
  );
  useEffect(() => {
    const uploads = controllers.current;
    return () => {
      for (const controller of uploads.values())
        void controller.pause().catch(() => {});
    };
  }, []);
  const append = (item: Evidence) => {
    current.current = [
      ...current.current.filter((value) => value.id !== item.id),
      item,
    ];
    onChange(current.current);
  };
  const changeJob = (id: string, patch: Partial<(typeof jobs)[string]>) =>
    setJobs((values) => ({ ...values, [id]: { ...values[id], ...patch } }));
  const start = (file: File) => {
    const id = crypto.randomUUID();
    setJobs((values) => ({
      ...values,
      [id]: { name: file.name, progress: 0, status: "uploading" },
    }));
    const controller = getServices().evidence.upload(
      file,
      { shownTimestamp: timestamp },
      {
        onProgress: (progress) =>
          changeJob(id, { progress, status: "uploading", error: undefined }),
        onError: (cause) =>
          changeJob(id, { status: "error", error: cause.message }),
      },
    );
    controllers.current.set(id, controller);
    void controller.done
      .then((item) => {
        append(item);
        changeJob(id, { status: "done", progress: 100 });
        controllers.current.delete(id);
      })
      .catch((cause: unknown) => {
        changeJob(id, {
          status:
            cause instanceof Error && cause.name === "AbortError"
              ? "cancelled"
              : "error",
          error: cause instanceof Error ? cause.message : "Chưa tải được tệp.",
        });
      });
  };
  const addNote = async () => {
    if (!note.trim()) return;
    setBusy(true);
    setError("");
    try {
      append(
        await getServices().evidence.createNote({
          originalText: note.trim(),
          shownTimestamp: timestamp,
        }),
      );
      setNote("");
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Chưa lưu được ghi chú.",
      );
    } finally {
      setBusy(false);
    }
  };
  const permanentDelete = async (item: Evidence) => {
    if (
      !window.confirm(
        "Xóa vĩnh viễn tệp hoặc ghi chú này? Thao tác không thể hoàn tác.",
      )
    )
      return;
    setError("");
    try {
      await getServices().evidence.remove(item.id);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Chưa xóa được nguồn. Vui lòng thử lại.",
      );
    }
  };
  return (
    <div className="stack evidence-picker">
      <Notice>
        Tệp được lưu riêng tư. Nội dung chưa được AI phân tích. Nếu tải bị gián
        đoạn, chọn lại cùng tệp để tiếp tục; tệp đã tải xong vẫn nằm trong mục
        chưa gắn hồ sơ.
      </Notice>
      <input
        ref={input}
        hidden
        aria-label="Chọn tệp bằng chứng"
        type="file"
        multiple
        accept="image/*,audio/*,video/*,application/pdf,*/*"
        onChange={(event) => {
          for (const file of Array.from(event.target.files ?? [])) start(file);
          event.target.value = "";
        }}
      />
      <Button
        type="button"
        variant="secondary"
        onClick={() => input.current?.click()}
      >
        <Paperclip size={18} />
        Thêm tệp
      </Button>
      {Object.entries(jobs).map(([id, job]) => (
        <div className="panel stack" key={id}>
          <strong>{job.name}</strong>
          <progress
            max={100}
            value={job.progress}
            aria-label={`Tiến độ tải ${job.name}`}
          />
          <span role="status">
            {job.status === "done"
              ? "Đã tải xong"
              : job.status === "paused"
                ? "Đã tạm dừng"
                : job.status === "cancelled"
                  ? "Đã hủy"
                  : `${Math.round(job.progress)}%`}
          </span>
          {job.error && job.status !== "cancelled" && (
            <Notice tone="error">{job.error}</Notice>
          )}
          {job.status !== "done" && job.status !== "cancelled" && (
            <div className="actions">
              {job.status === "uploading" ? (
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() =>
                    void controllers.current
                      .get(id)
                      ?.pause()
                      .then(() => changeJob(id, { status: "paused" }))
                      .catch((cause: Error) =>
                        changeJob(id, {
                          status: "error",
                          error: cause.message,
                        }),
                      )
                  }
                >
                  Tạm dừng
                </Button>
              ) : (
                <Button
                  type="button"
                  onClick={() =>
                    void controllers.current
                      .get(id)
                      ?.resume()
                      .then(() =>
                        changeJob(id, {
                          status: "uploading",
                          error: undefined,
                        }),
                      )
                      .catch((cause: Error) =>
                        changeJob(id, {
                          status: "error",
                          error: cause.message,
                        }),
                      )
                  }
                >
                  Tiếp tục tải
                </Button>
              )}
              <Button
                type="button"
                variant="ghost"
                onClick={() =>
                  void controllers.current
                    .get(id)
                    ?.cancel()
                    .then(() => changeJob(id, { status: "cancelled" }))
                    .catch((cause: Error) =>
                      changeJob(id, { status: "error", error: cause.message }),
                    )
                }
              >
                Hủy tải
              </Button>
            </div>
          )}
        </div>
      ))}
      <Field label="Ghi chú hoặc đoạn tin nhắn" id="real-evidence-note">
        <textarea
          id="real-evidence-note"
          rows={3}
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
      </Field>
      <Field
        label="Mốc thời gian hiển thị trong nội dung (nếu có)"
        value={timestamp}
        onChange={(event) => setTimestamp(event.target.value)}
      />
      <Button
        type="button"
        variant="secondary"
        disabled={busy || !note.trim()}
        onClick={() => void addNote()}
      >
        Thêm ghi chú
      </Button>
      {error && <Notice tone="error">{error}</Notice>}
      {!!items.length && (
        <ul className="evidence-attachments">
          {items.map((item) => (
            <li key={item.id}>
              <FileText size={20} />
              <div>
                <strong>{item.originalFilename ?? "Ghi chú"}</strong>
                <p>{item.originalText}</p>
                <Badge tone="gray">Đã lưu riêng tư</Badge>
              </div>
              <Button
                type="button"
                variant="ghost"
                aria-label={`Bỏ ${item.id}`}
                onClick={() =>
                  onChange(items.filter((value) => value.id !== item.id))
                }
              >
                <Trash2 size={18} />
              </Button>
            </li>
          ))}
        </ul>
      )}
      {!!available.length && (
        <section className="stack">
          <h3>Đã lưu, chưa gắn hồ sơ</h3>
          {available.map((item) => (
            <div key={item.id} className="list-row">
              <span>{item.originalFilename ?? item.originalText}</span>
              <Button
                type="button"
                variant="secondary"
                onClick={() => append(item)}
              >
                Chọn nguồn
              </Button>
              <Button
                type="button"
                variant="ghost"
                onClick={() => void permanentDelete(item)}
              >
                Xóa vĩnh viễn
              </Button>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}

function DemoEvidencePicker({
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
