import { useEffect, useRef, useState } from "react";
import { Button, cx } from "../../components/UI";
import { ApiError } from "../../api/client";
import { ErrorNotice, useSession } from "./RealApp";
import { encodeWav } from "./audio";
import type { ConsentInput, SessionView } from "../../api/contracts";

type Recording = {
  stream: MediaStream;
  context: AudioContext;
  node: AudioWorkletNode;
  chunks: Float32Array[];
  frames: number;
  timer: ReturnType<typeof setTimeout>;
  clock: ReturnType<typeof setInterval>;
};

export type TranscriptPlacement = "fill" | "append" | "replace";

/** The composer text after placing a transcript; null when it would exceed the limit. */
export function placeTranscript(draft: string, transcript: string, placement: TranscriptPlacement): string | null {
  const next = placement === "append" ? `${draft.trimEnd()} ${transcript.trim()}` : transcript.trim();
  return next.length > 500 ? null : next;
}

export function VoiceRecorder({ draft, onUse }: { draft: string; onUse: (text: string) => void }) {
  const { api, session, receive } = useSession();
  const allowed = session.features.voice;
  const authorized = session.consents.AI.enabled && session.consents.VOICE.enabled;
  const allowedRef = useRef(allowed);
  allowedRef.current = allowed && authorized;
  const [state, setState] = useState<
      "idle" | "starting" | "recording" | "transcribing" | "preview"
    >("idle"),
    [seconds, setSeconds] = useState(0),
    [text, setText] = useState(""),
    [error, setError] = useState<unknown>(),
    [placementError, setPlacementError] = useState("");
  const recording = useRef<Recording | undefined>(undefined),
    upload = useRef<AbortController | undefined>(undefined),
    alive = useRef(true);
  const cleanup = () => {
    const value = recording.current;
    if (value) {
      clearTimeout(value.timer);
      clearInterval(value.clock);
      value.stream.getTracks().forEach((track) => track.stop());
      value.node.disconnect();
      value.node.port.close();
      void value.context.close();
      recording.current = undefined;
    }
  };
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      cleanup();
      upload.current?.abort();
    };
  }, []);
  useEffect(() => {
    if (!allowed || (!authorized && state !== "idle" && state !== "starting")) {
      cleanup();
      upload.current?.abort();
      setText("");
      setState("idle");
    }
  }, [allowed, authorized, state]);
  async function finish() {
    const value = recording.current;
    if (!value) return;
    cleanup();
    if (!value.frames) {
      // Nothing was captured yet: say so instead of uploading an empty file.
      setError(new ApiError(422, "RECORDING_TOO_SHORT", "Bản ghi quá ngắn để chuyển thành chữ. Bạn hãy ghi âm lại hoặc nhập tin nhắn."));
      setState("idle");
      return;
    }
    setState("transcribing");
    const controller = new AbortController();
    upload.current = controller;
    const timeout = setTimeout(() => controller.abort(), 40000);
    try {
      const blob = encodeWav(value.chunks, value.context.sampleRate);
      value.chunks.length = 0;
      const response = await fetch("/api/v1/voice/transcriptions", {
        method: "POST",
        credentials: "same-origin",
        cache: "no-store",
        body: blob,
        signal: controller.signal,
        headers: {
          "Content-Type": "audio/wav",
          "X-CSRF-Token": session.csrfToken,
          "Idempotency-Key": crypto.randomUUID(),
        },
      });
      if (!response.ok)
        throw new ApiError(
          response.status,
          "VOICE_FAILED",
          "Chưa chuyển được giọng nói thành chữ. Bạn vẫn có thể nhập tin nhắn.",
        );
      const result = await response.json();
      if (
        typeof result.text !== "string" ||
        Array.from(result.text).length > 500
      )
        throw new ApiError(502, "INVALID_TRANSCRIPT", "Chưa nhận được bản chép lời hợp lệ. Bạn vẫn có thể nhập tin nhắn.");
      if (alive.current) {
        setText(result.text);
        setState("preview");
      }
    } catch (reason) {
      if (alive.current) {
        setError(reason);
        setState("idle");
      }
    } finally {
      clearTimeout(timeout);
      upload.current = undefined;
      value.chunks.length = 0;
    }
  }
  async function start() {
    setError(undefined);
    setState("starting");
    let stream: MediaStream | undefined, context: AudioContext | undefined;
    try {
      let next = session;
      for (const purpose of ["AI", "VOICE"] as const) {
        if (!next.consents[purpose].enabled) {
          next = await api.request<SessionView>(`/consents/${purpose}`, {
            method: "PUT",
            body: { enabled: true, expectedVersion: next.consents[purpose].version,
                    policyVersion: "v1" } satisfies ConsentInput,
          });
          receive(next);
        }
      }
      if (!alive.current) return;
      allowedRef.current = true;
      if (!navigator.mediaDevices?.getUserMedia || !window.AudioContext)
        throw new ApiError(
          422,
          "MIC_UNAVAILABLE",
          "Trình duyệt này chưa hỗ trợ ghi âm. Bạn vẫn có thể nhập tin nhắn.",
        );
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true },
        video: false,
      });
      if (!alive.current || !allowedRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      context = new AudioContext({ sampleRate: 16000 });
      await context.audioWorklet.addModule(
        new URL("./pcm-worklet.js", import.meta.url),
      );
      if (!alive.current || !allowedRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        await context.close();
        return;
      }
      const node = new AudioWorkletNode(context, "moodprint-pcm"),
        source = context.createMediaStreamSource(stream),
        mute = context.createGain();
      mute.gain.value = 0;
      source.connect(node);
      node.connect(mute);
      mute.connect(context.destination);
      await context.resume();
      if (!alive.current || !allowedRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        node.disconnect();
        node.port.close();
        await context.close();
        return;
      }
      const value: Recording = {
        stream,
        context,
        node,
        chunks: [],
        frames: 0,
        timer: setTimeout(() => void finish(), 30000),
        clock: setInterval(
          () => setSeconds((value) => Math.min(30, value + 1)),
          1000,
        ),
      };
      node.port.onmessage = (event) => {
        if (recording.current !== value) return;
        const data = event.data as Float32Array;
        const remaining = value.context.sampleRate * 30 - value.frames;
        if (remaining > 0) {
          const chunk = data.slice(0, remaining);
          value.chunks.push(chunk);
          value.frames += chunk.length;
        }
        if (value.frames >= value.context.sampleRate * 30) void finish();
      };
      recording.current = value;
      setSeconds(0);
      setState("recording");
    } catch (reason) {
      stream?.getTracks().forEach((track) => track.stop());
      if (context) void context.close();
      setError(reason);
      setState("idle");
    }
  }
  if (!session.features.voice)
    return null;
  return (
    <section className="real-voice" aria-label="Nhập bằng giọng nói">
      <p className={cx.footnote}>Chỉ ghi sau khi bạn chọn Ghi âm và trình duyệt cho phép. Âm thanh được gửi đến OpenAI để chuyển thành chữ, không lưu bản âm thanh; bạn xem và sửa chữ trước khi gửi.</p>
      <ErrorNotice error={error} />
      {state === "idle" && (
        <Button variant="text" onClick={() => void start()}>
          Ghi âm tối đa 30 giây
        </Button>
      )}
      {state === "starting" ? <p role="status">Đang chờ quyền dùng micro…</p> : null}
      {state === "recording" && (
        <>
          <p role="status">Đang ghi âm · {seconds}/30 giây</p>
          <div className={cx.actions}>
            <Button variant="secondary" onClick={() => void finish()}>
              Dừng và chuyển thành văn bản
            </Button>
            <Button
              variant="text"
              onClick={() => {
                cleanup();
                setState("idle");
              }}
            >
              Hủy ghi âm
            </Button>
          </div>
        </>
      )}
      {state === "transcribing" && (
        <>
          <p role="status">Đang chuyển giọng nói thành chữ…</p>
          <Button
            variant="text"
            onClick={() => {
              upload.current?.abort();
              setState("idle");
            }}
          >
            Hủy chuyển thành văn bản
          </Button>
        </>
      )}
      {state === "preview" && (
        <>
          <label htmlFor="voice-preview">Xem và sửa bản chép lời</label>
          <textarea
            id="voice-preview"
            maxLength={500}
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
          <p>
            Bản chép lời chưa được gửi. Bạn quyết định có dùng nội dung này hay
            không.
          </p>
          {draft.trim() ? <p>Ô tin nhắn đang có nội dung bạn soạn.</p> : null}
          {placementError ? <p role="alert">{placementError}</p> : null}
          <div className={cx.actions}>
            {(draft.trim() ? (["append", "replace"] as const) : (["fill"] as const)).map((placement) => (
              <Button
                key={placement}
                variant="secondary"
                disabled={!text.trim()}
                onClick={() => {
                  const next = placeTranscript(draft, text, placement);
                  if (next === null) {
                    setPlacementError("Nội dung sau khi thêm sẽ dài hơn 500 ký tự. Hãy rút gọn bản chép lời hoặc chọn Thay nội dung.");
                    return;
                  }
                  onUse(next);
                  setPlacementError("");
                  setText("");
                  setState("idle");
                }}
              >
                {placement === "fill" ? "Đưa vào ô tin nhắn" : placement === "append" ? "Thêm vào tin nhắn" : "Thay nội dung"}
              </Button>
            ))}
            <Button
              variant="text"
              onClick={() => {
                setPlacementError("");
                setText("");
                setState("idle");
              }}
            >
              {draft.trim() ? "Giữ tin nhắn đang soạn" : "Bỏ bản chép lời"}
            </Button>
          </div>
        </>
      )}
    </section>
  );
}
