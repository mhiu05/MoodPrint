import { useEffect, useRef, useState } from "react";
import { ApiError, type ApiClient } from "../../../api/client";
import type { MapsSearchView } from "../../../api/contracts";
import { safeSourceUrl } from "../../../api/stream";
import { Button } from "../../../components/UI";

export function PlacesCard({ places }: { places: NonNullable<MapsSearchView["places"]> }) {
  return <section className="maps-search-card" aria-label="Địa điểm đã dùng cho gợi ý"><strong>Địa điểm từ Google Maps qua Apify</strong><ol>{places.slice(0, 5).map((place, i) =>
    <li key={place.placeId ?? i}><strong>{place.name}</strong>{place.category ? <p>{place.category}</p> : null}<p>{place.address}</p>
      {place.rating != null ? <p>Đánh giá {place.rating}/5{place.ratingCount != null ? ` (${place.ratingCount})` : ""}</p> : null}
      {place.openingHours?.length ? <p>{place.openingHours.join(" · ")}</p> : null}
      <small>Dữ liệu lúc {new Date(place.fetchedAt).toLocaleString("vi-VN")}. Giờ và đánh giá có thể thay đổi.</small><br />
      {safeSourceUrl(place.mapsUrl) && new URL(place.mapsUrl).hostname === "www.google.com" && new URL(place.mapsUrl).pathname.startsWith("/maps/") ? <a href={place.mapsUrl} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer">Mở Google Maps</a> : null}
    </li>)}</ol></section>;
}

export function MapsSearchCard({ api, searchId, onReuse }: { api: ApiClient; searchId: string; onReuse: (id: string) => void }) {
  const [view, setView] = useState<MapsSearchView>(), [error, setError] = useState(false), [revision, setRevision] = useState(0), [visible, setVisible] = useState(true);
  const [unavailable, setUnavailable] = useState(false);
  const root = useRef<HTMLElement>(null);
  const polling = useRef<AbortController | null>(null);
  const finished = useRef<string | null>(null);
  useEffect(() => {
    const observer = new IntersectionObserver(entries => setVisible(entries.some(e => e.isIntersecting)));
    if (root.current) observer.observe(root.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    if (!visible) return;
    const controller = new AbortController();
    polling.current = controller;
    let timer: ReturnType<typeof setTimeout> | undefined, since = Date.now();
    async function poll() {
      if (controller.signal.aborted || document.hidden || finished.current === searchId) return;
      try {
        const next = await api.request<MapsSearchView>(`/ai/maps-searches/${encodeURIComponent(searchId)}`, { signal: controller.signal });
        if (controller.signal.aborted) return;
        setView(next); setError(false);
        if (!["starting", "pending"].includes(next.status)) finished.current = searchId;
        if (["starting", "pending"].includes(next.status) && Date.now() - since < 90_000)
          timer = setTimeout(() => void poll(), Date.now() - since < 30_000 ? 2000 : 5000);
      } catch (reason) {
        if (controller.signal.aborted) return;
        if (reason instanceof ApiError && reason.code === "MAPS_NOT_FOUND") {
          finished.current = searchId;
          setUnavailable(true); setError(false);
        } else setError(true);
      }
    }
    const visibility = () => { if (document.hidden) clearTimeout(timer); else { since = Date.now(); void poll(); } };
    document.addEventListener("visibilitychange", visibility);
    void poll();
    return () => { controller.abort(); clearTimeout(timer); document.removeEventListener("visibilitychange", visibility); };
  }, [api, searchId, visible, revision]);
  async function cancel() {
    if (!view) return;
    try {
      const cancelled = await api.request<MapsSearchView>(`/ai/maps-searches/${searchId}/cancel`, { method: "POST", body: { expectedVersion: view.version } });
      // A pending GET/timer must not overwrite the acknowledged cancellation.
      finished.current = searchId;
      polling.current?.abort();
      setView(cancelled); setError(false);
    } catch { setError(true); }
  }
  if (unavailable) return <section className="maps-search-card" ref={root} aria-label="Kết quả tìm địa điểm">
    <strong>Địa điểm từ Google Maps qua Apify</strong>
    <p>Kết quả không còn khả dụng. Bạn có thể chọn tìm kiếm cho một lượt mới.</p>
  </section>;
  return <section className="maps-search-card" ref={root} aria-label="Kết quả tìm địa điểm">
    <strong>Địa điểm từ Google Maps qua Apify</strong>
    {error ? <p role="status">Chưa tải được thẻ. <button type="button" onClick={() => setRevision(r => r+1)}>Thử tải lại</button></p> : !view || ["starting", "pending"].includes(view.status) ? <p role="status">Đang tìm địa điểm…{view ? <Button variant="text" onClick={() => void cancel()}>Dừng tìm địa điểm</Button> : null}</p> : null}
    {view?.status === "ready" ? <><ol>{view.places?.slice(0,5).map((place, index) => <li key={place.placeId ?? index}>
      <strong>{place.name}</strong>{place.category ? <p>{place.category}</p> : null}<p>{place.address}</p>
      {place.rating != null ? <p>Đánh giá {place.rating}/5{place.ratingCount != null ? ` (${place.ratingCount})` : ""}</p> : null}
      {place.openingHours?.length ? <p>{place.openingHours.join(" · ")}</p> : null}
      <small>Dữ liệu lúc {new Date(place.fetchedAt).toLocaleString("vi-VN")}. Giờ và đánh giá có thể thay đổi.</small><br />
      {safeSourceUrl(place.mapsUrl) && new URL(place.mapsUrl).hostname === "www.google.com" && new URL(place.mapsUrl).pathname.startsWith("/maps/") ? <a href={place.mapsUrl} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer">Mở Google Maps</a> : null}
    </li>)}</ol><Button variant="secondary" onClick={() => onReuse(searchId)}>Nhờ trợ lý gợi ý từ kết quả</Button></> : view && !["starting", "pending"].includes(view.status) ? <p>{view.status === "empty" ? "Chưa tìm thấy địa điểm phù hợp." : view.status === "cancelled" ? "Đã yêu cầu dừng tìm địa điểm." : view.status === "expired" ? "Kết quả đã hết hạn. Bạn có thể chọn tìm kiếm cho một lượt mới." : "Chưa hoàn tất tìm địa điểm. Không tự chạy lại lượt trả phí."}</p> : null}
  </section>;
}
