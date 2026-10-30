import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import {
  ImagePlus,
  Mic,
  Pause,
  Play,
  Square,
  Trash2,
  Upload,
  Video,
  X,
} from "lucide-react";
import { Button } from "../../../components/UI";
import { ApiError } from "../../../api/client";
import {
  uploadJournalFile,
  type JournalEntry,
  type JournalMediaType,
  type JournalUpload,
} from "../../../api/journal";
import { ErrorNotice, useSession } from "../RealApp";
import { JournalMediaPreview } from "./JournalShared";

type PendingFile = {
  key: string;
  file: File;
  url: string;
  type: JournalMediaType;
  duration?: number;
  reservation?: JournalUpload;
  state: "queued" | "uploading" | "failed";
  progress: number;
  error?: unknown;
};
export type JournalAttachmentsHandle = {
  flush: (entry: JournalEntry) => Promise<JournalEntry>;
  hasPending: () => boolean;
};
type Props = {
  entry?: JournalEntry;
  ensureEntry: () => Promise<JournalEntry>;
  onEntry: (entry: JournalEntry) => void;
  onPending: (pending: boolean) => void;
  onBusy: (busy: boolean) => void;
  disabled?: boolean;
};

const limits = { image: 10, audio: 20, video: 50 };
const allowedMimes =
  /^(image\/(jpeg|png|webp|gif)|audio\/(webm|ogg|mp4|mpeg|wav)|video\/(mp4|webm|quicktime))$/;

export const JournalAttachments = forwardRef<JournalAttachmentsHandle, Props>(
  function JournalAttachments(
    { entry, ensureEntry, onEntry, onPending, onBusy, disabled },
    ref,
  ) {
    const { api } = useSession();
    const [files, setFiles] = useState<PendingFile[]>([]);
    const filesRef = useRef<PendingFile[]>([]);
    const [error, setError] = useState<unknown>();
    const [uploading, setUploading] = useState(false);
    const uploadBusy = useRef(false),
      controller = useRef<AbortController | null>(null),
      alive = useRef(true);
    const [recordState, setRecordState] = useState<
      "idle" | "starting" | "recording" | "paused"
    >("idle");
    const recordAttempt = useRef(0);
    const [seconds, setSeconds] = useState(0);
    const recorder = useRef<MediaRecorder | null>(null),
      stream = useRef<MediaStream | null>(null),
      recordTimer = useRef<ReturnType<typeof setInterval> | null>(null),
      elapsed = useRef(0),
      cancelledRecording = useRef(false);
    const urls = useRef(new Set<string>());
    const publish = (next: PendingFile[]) => {
      filesRef.current = next;
      setFiles(next);
      onPending(
        next.length > 0 ||
          recorder.current?.state === "recording" ||
          recorder.current?.state === "paused",
      );
    };
    const update = (key: string, patch: Partial<PendingFile>) =>
      publish(
        filesRef.current.map((item) =>
          item.key === key ? { ...item, ...patch } : item,
        ),
      );
    const stopTracks = () => {
      stream.current?.getTracks().forEach((track) => track.stop());
      stream.current = null;
      if (recordTimer.current) clearInterval(recordTimer.current);
      recordTimer.current = null;
    };
    useEffect(() => {
      alive.current = true;
      return () => {
        alive.current = false;
        cancelledRecording.current = true;
        if (recorder.current && recorder.current.state !== "inactive")
          recorder.current.stop();
        stopTracks();
        controller.current?.abort();
        urls.current.forEach((url) => URL.revokeObjectURL(url));
      };
    }, []);

    function add(fileList: File[], duration?: number) {
      setError(undefined);
      const next = [...filesRef.current];
      for (const file of fileList) {
        const mime = file.type.split(";")[0];
        const type = mime.split("/")[0] as JournalMediaType;
        if (!allowedMimes.test(mime)) {
          setError(
            new ApiError(
              422,
              "MEDIA_TYPE",
              "Tệp chưa được hỗ trợ. Chọn ảnh JPG, PNG, WebP, GIF; âm thanh WAV, MP3, M4A, WebM, OGG; video MP4, WebM hoặc MOV.",
            ),
          );
          continue;
        }
        if (!file.size || file.size > limits[type] * 1024 * 1024) {
          setError(
            new ApiError(
              422,
              "MEDIA_SIZE",
              `Tệp ${file.name} cần có dữ liệu và không quá ${limits[type]} MB.`,
            ),
          );
          continue;
        }
        if (next.length + (entry?.media.length || 0) >= 10) {
          setError(
            new ApiError(
              422,
              "MEDIA_LIMIT",
              "Mỗi khoảnh khắc có tối đa 10 tệp. Gỡ một tệp trước khi thêm.",
            ),
          );
          break;
        }
        const url = URL.createObjectURL(file);
        urls.current.add(url);
        next.push({
          key: crypto.randomUUID(),
          file,
          url,
          type,
          duration,
          state: "queued",
          progress: 0,
        });
      }
      publish(next);
    }
    async function startRecording() {
      setError(undefined);
      const attempt = ++recordAttempt.current;
      setRecordState("starting");
      onBusy(true);
      onPending(true);
      try {
        if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder)
          throw new ApiError(
            422,
            "MIC_UNAVAILABLE",
            "Trình duyệt chưa hỗ trợ ghi âm. Bạn có thể tải lên một tệp âm thanh.",
          );
        const microphone = await navigator.mediaDevices.getUserMedia({
          audio: true,
        });
        if (!alive.current || recordAttempt.current !== attempt) {
          microphone.getTracks().forEach((track) => track.stop());
          return;
        }
        stream.current = microphone;
        const mimeType = ["audio/webm", "audio/mp4", "audio/ogg"].find((type) =>
          MediaRecorder.isTypeSupported(type),
        );
        const instance = new MediaRecorder(
          microphone,
          mimeType ? { mimeType } : undefined,
        );
        const chunks: BlobPart[] = [];
        elapsed.current = 0;
        cancelledRecording.current = false;
        setSeconds(0);
        instance.ondataavailable = (event) => {
          if (event.data.size) chunks.push(event.data);
        };
        instance.onstop = () => {
          stopTracks();
          recorder.current = null;
          if (!alive.current) return;
          setRecordState("idle");
          onBusy(false);
          if (!cancelledRecording.current) {
            const mime = instance.mimeType.split(";")[0] || "audio/webm";
            const file = new File(
              chunks,
              `Ghi âm ${new Date().toLocaleTimeString("vi-VN").replace(/:/g, "-")}.${mime.includes("mp4") ? "m4a" : mime.includes("ogg") ? "ogg" : "webm"}`,
              { type: mime },
            );
            add([file], elapsed.current);
          } else onPending(filesRef.current.length > 0);
        };
        recorder.current = instance;
        instance.start(500);
        setRecordState("recording");
        onPending(true);
        onBusy(true);
        recordTimer.current = setInterval(() => {
          if (instance.state === "recording") {
            elapsed.current++;
            setSeconds(elapsed.current);
            if (elapsed.current >= 600) instance.stop();
          }
        }, 1000);
      } catch (reason) {
        stopTracks();
        if (alive.current && recordAttempt.current === attempt) {
          setRecordState("idle");
          onBusy(false);
          onPending(filesRef.current.length > 0);
          setError(
            reason instanceof ApiError
              ? reason
              : new ApiError(
                  422,
                  "MIC_DENIED",
                  "Chưa có quyền dùng micro. Cho phép micro trong trình duyệt rồi thử lại, hoặc tải tệp âm thanh.",
                ),
          );
        }
      }
    }
    async function flush(saved: JournalEntry): Promise<JournalEntry> {
      if (uploadBusy.current)
        throw new ApiError(
          409,
          "UPLOAD_BUSY",
          "Đang tải tệp, hãy đợi hoàn tất.",
        );
      uploadBusy.current = true;
      setUploading(true);
      onBusy(true);
      setError(undefined);
      let current = saved;
      try {
        for (const pending of [...filesRef.current]) {
          update(pending.key, { state: "uploading", error: undefined });
          try {
            const descriptor =
              pending.reservation ||
              (await api.request<JournalUpload>(
                `/journal/entries/${saved.id}/media`,
                {
                  method: "POST",
                  body: {
                    type: pending.type,
                    mimeType: pending.file.type.split(";")[0],
                    sizeBytes: pending.file.size,
                    ...(pending.duration === undefined
                      ? {}
                      : { durationSeconds: pending.duration }),
                  },
                },
              ));
            update(pending.key, { reservation: descriptor });
            let completed = false;
            if (pending.reservation) {
              try {
                await api.request(
                  `/journal/entries/${saved.id}/media/${descriptor.media.id}/complete`,
                  { method: "POST", body: {} },
                );
                completed = true;
              } catch (reason) {
                if (!(
                  reason instanceof ApiError &&
                  reason.status === 409 &&
                  reason.code === "UPLOAD_INCOMPLETE"
                ))
                  throw reason;
              }
            }
            if (!completed) {
              controller.current = new AbortController();
              await uploadJournalFile(
                descriptor,
                pending.file,
                controller.current.signal,
                (percent) => {
                  if (alive.current) update(pending.key, { progress: percent });
                },
              );
              await api.request(
                `/journal/entries/${saved.id}/media/${descriptor.media.id}/complete`,
                { method: "POST", body: {} },
              );
            }
            current = await api.request<JournalEntry>(
              `/journal/entries/${saved.id}`,
            );
            if (!alive.current) return current;
            onEntry(current);
            URL.revokeObjectURL(pending.url);
            urls.current.delete(pending.url);
            publish(
              filesRef.current.filter((item) => item.key !== pending.key),
            );
          } catch (reason) {
            const failure =
              reason instanceof ApiError
                ? reason
                : new ApiError(
                    503,
                    "UPLOAD_FAILED",
                    "Chưa tải được tệp. Giữ trang mở và thử tải lại.",
                  );
            if (alive.current)
              update(pending.key, { state: "failed", error: failure });
            throw failure;
          }
        }
        return current;
      } finally {
        uploadBusy.current = false;
        if (alive.current) {
          setUploading(false);
          onBusy(false);
        }
      }
    }
    useImperativeHandle(ref, () => ({
      flush,
      hasPending: () => filesRef.current.length > 0,
    }));
    async function uploadNow() {
      try {
        const saved = await ensureEntry();
        await flush(saved);
      } catch (reason) {
        if (alive.current) setError(reason);
      }
    }
    async function removeFile(pending: PendingFile) {
      setError(undefined);
      try {
        if (pending.reservation && entry)
          await api.request(
            `/journal/entries/${entry.id}/media/${pending.reservation.media.id}`,
            { method: "DELETE", body: {} },
          );
        URL.revokeObjectURL(pending.url);
        urls.current.delete(pending.url);
        publish(filesRef.current.filter((item) => item.key !== pending.key));
      } catch (reason) {
        setError(reason);
      }
    }
    async function removeSaved(mediaId: string) {
      if (!entry) return;
      setError(undefined);
      setUploading(true);
      onBusy(true);
      try {
        await api.request(`/journal/entries/${entry.id}/media/${mediaId}`, {
          method: "DELETE",
          body: {},
        });
        const fresh = await api.request<JournalEntry>(
          `/journal/entries/${entry.id}`,
        );
        onEntry(fresh);
      } catch (reason) {
        setError(reason);
      } finally {
        setUploading(false);
        onBusy(false);
      }
    }
    const blocked = disabled || uploading || recordState !== "idle";
    return (
      <section
        className="journal-attachments"
        aria-labelledby="journal-attachments-title"
      >
        <h3 id="journal-attachments-title">Tải lên</h3>
        <div className="journal-media-tools">
          <label className="journal-file-tool">
            <ImagePlus size={19} />
            Hình ảnh
            <input
              type="file"
              multiple
              accept="image/jpeg,image/png,image/webp,image/gif"
              aria-label="Thêm hình ảnh"
              disabled={blocked}
              onChange={(event) => {
                add(Array.from(event.target.files || []));
                event.target.value = "";
              }}
            />
          </label>
          <button
            type="button"
            disabled={blocked}
            onClick={() => void startRecording()}
          >
            <Mic size={19} />
            Ghi âm
          </button>
          <label className="journal-file-tool">
            <Upload size={18} />
            Âm thanh
            <input
              type="file"
              multiple
              accept="audio/*"
              aria-label="Thêm âm thanh"
              disabled={blocked}
              onChange={(event) => {
                add(Array.from(event.target.files || []));
                event.target.value = "";
              }}
            />
          </label>
          <label className="journal-file-tool">
            <Video size={19} />
            Video
            <input
              type="file"
              multiple
              accept="video/mp4,video/webm,video/quicktime"
              aria-label="Thêm video"
              disabled={blocked}
              onChange={(event) => {
                add(Array.from(event.target.files || []));
                event.target.value = "";
              }}
            />
          </label>
        </div>
        <p className="journal-help">
          Ảnh tối đa 10 MB · âm thanh 20 MB · video 50 MB · tối đa 10 tệp.
        </p>
        {recordState === "starting" ? (
          <div className="journal-recording">
            <p role="status">Đang chờ quyền dùng micro…</p>
            <Button
              variant="text"
              onClick={() => {
                recordAttempt.current++;
                setRecordState("idle");
                onBusy(false);
                onPending(filesRef.current.length > 0);
              }}
            >
              Hủy chờ micro
            </Button>
          </div>
        ) : recordState !== "idle" ? (
          <div className="journal-recording">
            <p role="status">
              <Mic size={18} />
              {recordState === "paused" ? "Đã tạm dừng" : "Đang ghi âm"} ·{" "}
              {Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, "0")}{" "}
              / 10:00
            </p>
            <div className="actions">
              <Button
                variant="secondary"
                onClick={() => {
                  if (recordState === "recording") {
                    recorder.current?.pause();
                    setRecordState("paused");
                  } else {
                    recorder.current?.resume();
                    setRecordState("recording");
                  }
                }}
              >
                {recordState === "recording" ? (
                  <Pause size={17} />
                ) : (
                  <Play size={17} />
                )}
                {recordState === "recording"
                  ? "Tạm dừng ghi âm"
                  : "Tiếp tục ghi âm"}
              </Button>
              <Button
                variant="secondary"
                onClick={() => {
                  recorder.current?.stop();
                  onBusy(false);
                }}
              >
                <Square size={17} />
                Dừng ghi âm
              </Button>
              <Button
                variant="text"
                onClick={() => {
                  cancelledRecording.current = true;
                  recorder.current?.stop();
                  onBusy(false);
                }}
              >
                Hủy ghi âm
              </Button>
            </div>
          </div>
        ) : null}
        <ErrorNotice error={error} />
        {entry?.media.map((media) => (
          <div className="journal-saved-media" key={media.id}>
            <JournalMediaPreview entryId={entry.id} media={media} />
            <Button
              variant="text"
              disabled={blocked}
              onClick={() => void removeSaved(media.id)}
              aria-label={`Gỡ ${media.type === "image" ? "ảnh" : media.type === "audio" ? "ghi âm" : "video"} đã lưu`}
            >
              <Trash2 size={17} />
              Gỡ tệp
            </Button>
          </div>
        ))}
        {files.length ? (
          <div className="journal-pending-files">
            {files.map((file) => (
              <div className="journal-pending-file" key={file.key}>
                {file.type === "image" ? (
                  <img src={file.url} alt={`Xem trước ${file.file.name}`} />
                ) : file.type === "audio" ? (
                  <audio
                    controls
                    preload="metadata"
                    src={file.url}
                    aria-label={`Nghe lại ${file.file.name}`}
                  />
                ) : (
                  <video
                    controls
                    preload="metadata"
                    src={file.url}
                    aria-label={`Xem trước ${file.file.name}`}
                  />
                )}
                <div className="journal-file-meta">
                  <span>{file.file.name}</span>
                  <small>
                    {(file.file.size / 1024 / 1024).toFixed(1)} MB ·{" "}
                    {file.state === "uploading"
                      ? `Đang tải ${Math.round(file.progress)}%`
                      : file.state === "failed"
                        ? "Chưa tải được"
                        : "Chưa tải lên"}
                  </small>
                </div>
                {file.state === "uploading" ? (
                  <progress
                    value={file.progress}
                    max={100}
                    aria-label={`Tiến độ tải ${file.file.name}`}
                  />
                ) : null}
                {file.state === "failed" ? (
                  <Button
                    variant="secondary"
                    disabled={blocked}
                    onClick={() => void uploadNow()}
                    aria-label={`Thử tải lại ${file.file.name}`}
                  >
                    Thử tải lại
                  </Button>
                ) : null}
                <button
                  className="journal-remove-file"
                  type="button"
                  disabled={blocked}
                  aria-label={`Gỡ ${file.file.name}`}
                  onClick={() => void removeFile(file)}
                >
                  <X size={18} />
                </button>
              </div>
            ))}
          </div>
        ) : null}
        {files.length ? (
          <Button
            variant="secondary"
            disabled={blocked}
            onClick={() => void uploadNow()}
          >
            <Upload size={17} />
            {uploading ? "Đang tải tệp…" : "Tải tệp đính kèm"}
          </Button>
        ) : null}
      </section>
    );
  },
);
