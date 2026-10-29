/** Transient path-scoped capabilities; no cookies, provider session, or persistent resume keys. */
export type UploadDescriptor = {
  uploadUrl: string;
  token: string;
  resumableUrl: string;
  objectPath: string;
  bucket: string;
};

export async function uploadJournalBytes(
  descriptor: UploadDescriptor,
  file: Blob,
  signal?: AbortSignal,
  onProgress?: (percent: number) => void,
): Promise<void> {
  if (signal?.aborted) throw new DOMException("Đã hủy tải tệp.", "AbortError");
  if (file.size <= 6 * 1024 * 1024) {
    await new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const abort = () => xhr.abort();
      const finish = (error?: Error) => {
        signal?.removeEventListener("abort", abort);
        if (error) reject(error);
        else resolve();
      };
      xhr.open("PUT", descriptor.uploadUrl);
      xhr.setRequestHeader(
        "Content-Type",
        file.type.split(";")[0] || "application/octet-stream",
      );
      xhr.setRequestHeader("x-upsert", "false");
      xhr.timeout = 120_000;
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable)
          onProgress?.(Math.round((event.loaded / event.total) * 100));
      };
      xhr.onload = () =>
        finish(
          xhr.status >= 200 && xhr.status < 300
            ? undefined
            : new Error("Chưa tải được tệp. Bạn hãy thử lại."),
        );
      xhr.onerror = xhr.ontimeout = () =>
        finish(new Error("Kết nối bị gián đoạn. Bạn hãy thử lại tệp này."));
      xhr.onabort = () =>
        finish(new DOMException("Đã hủy tải tệp.", "AbortError"));
      signal?.addEventListener("abort", abort, { once: true });
      xhr.send(file);
    });
    onProgress?.(100);
    return;
  }
  // Load TUS only when needed. Resume metadata is RAM-only to avoid leaking private paths in storage.
  const { Upload } = await import("tus-js-client");
  await new Promise<void>((resolve, reject) => {
    const abort = () => {
      void upload.abort();
      finish(new DOMException("Đã hủy tải tệp.", "AbortError"));
    };
    const finish = (error?: Error) => {
      signal?.removeEventListener("abort", abort);
      if (error) reject(error);
      else resolve();
    };
    const upload = new Upload(file, {
      endpoint: descriptor.resumableUrl,
      headers: { "x-signature": descriptor.token, "x-upsert": "false" },
      metadata: {
        bucketName: descriptor.bucket,
        objectName: descriptor.objectPath,
        contentType: file.type.split(";")[0],
      },
      chunkSize: 6 * 1024 * 1024,
      retryDelays: [0, 1000, 3000, 5000],
      uploadDataDuringCreation: true,
      storeFingerprintForResuming: false,
      removeFingerprintOnSuccess: true,
      onProgress: (sent, total) =>
        onProgress?.(Math.round((sent / total) * 100)),
      onError: () =>
        finish(new Error("Chưa tải xong tệp. Giữ trang mở và thử lại.")),
      onSuccess: () => finish(),
    });
    signal?.addEventListener("abort", abort, { once: true });
    upload.start();
  });
}
