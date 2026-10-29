import {
  ArrowRight,
  CalendarDays,
  Images,
  Lightbulb,
  BarChart3,
} from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { BotAvatar } from "../../../companions/Avatar";
import type { JournalCollection, JournalEntry } from "../../../api/journal";
import { Button } from "../../../components/UI";
import { ErrorNotice, useResource, useSession } from "../RealApp";
import { localDate } from "../Mood";
import { JournalEditor } from "./JournalEditor";
import { JournalEntryCard, JournalNav } from "./JournalShared";
import { entryQuery, formatJournalDate, writingPrompts } from "./journalModel";
import "./journal.css";

export function useJournalToday() {
  const { session } = useSession();
  const offset = useMemo(
    () => new Date(session.serverTime).getTime() - Date.now(),
    [session.serverTime],
  );
  const [clock, setClock] = useState(Date.now);
  useEffect(() => {
    const tick = () => setClock(Date.now());
    const interval = setInterval(tick, 60_000);
    window.addEventListener("focus", tick);
    document.addEventListener("visibilitychange", tick);
    return () => {
      clearInterval(interval);
      window.removeEventListener("focus", tick);
      document.removeEventListener("visibilitychange", tick);
    };
  }, []);
  return localDate(clock + offset, session.timezone);
}

export function JournalPage() {
  const today = useJournalToday();
  const [params] = useSearchParams();
  const seedDate = params.get("date") || today;
  const drafts = useResource<JournalCollection>(
    `/journal/entries?${entryQuery({ status: "draft", limit: 5 })}`,
  );
  const recent = useResource<JournalCollection>(
    `/journal/entries?${entryQuery({ limit: 3 })}`,
  );
  const promptNumber = Number(params.get("prompt"));
  const prompt =
    params.has("prompt") && Number.isInteger(promptNumber)
      ? writingPrompts[promptNumber]
      : undefined;
  function saved() {
    drafts.refresh();
    recent.refresh();
  }
  return (
    <div className="journal-page">
      <JournalNav />
      <header className="journal-intro">
        <div>
          <h1 tabIndex={-1} data-tour="mood-entry">
            Nhật ký cảm xúc
          </h1>
          <p>
            Ghi lại cảm xúc, lưu giữ khoảnh khắc
            <br className="journal-desktop-break" /> và hiểu mình hơn mỗi ngày.
          </p>
        </div>
        <BotAvatar id="may" size={96} />
      </header>
      <div className="journal-layout">
        <div className="journal-main-column">
          {drafts.data?.items.length ? (
            <details className="journal-drafts">
              <summary>{drafts.data.total} bản nháp đã lưu</summary>
              <ul>
                {drafts.data.items.map((draft) => (
                  <li key={draft.id}>
                    <span>
                      {formatJournalDate(draft.localDate)} ·{" "}
                      {draft.text.slice(0, 60) || "Chưa có lời viết"}
                    </span>
                    <Link to={`/self/entry/${draft.id}`}>
                      Mở bản nháp
                      <span className="sr-only">
                        {" "}
                        ngày {formatJournalDate(draft.localDate)}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
          <ErrorNotice error={drafts.error} retry={drafts.refresh} />
          <JournalEditor
            key={`${params.get("date") || "current"}-${params.get("prompt") || ""}`}
            today={today}
            seedDate={seedDate}
            prompt={prompt}
            onSaved={saved}
          />
        </div>
        <aside
          className="journal-discovery"
          aria-labelledby="journal-discovery-title"
        >
          <h2 id="journal-discovery-title">Khám phá thêm</h2>
          <div className="journal-discovery-links">
            <Link
              to="/self/companion"
              className="journal-discovery-link journal-nhip"
            >
              <BotAvatar id="nhip" size={54} />
              <div>
                <h3>Nhịp đồng hành</h3>
                <p>Cùng Nhịp nhìn lại và hiểu cảm xúc của bạn.</p>
              </div>
              <ArrowRight size={19} />
            </Link>
            <Link
              to="/self?prompt=0#journal-writing-title"
              className="journal-discovery-link"
            >
              <span className="journal-discovery-icon prompt">
                <Lightbulb size={25} />
              </span>
              <div>
                <h3>Gợi ý viết</h3>
                <p>Một câu hỏi nhỏ để bắt đầu.</p>
              </div>
              <ArrowRight size={19} />
            </Link>
            <Link to="/self/memories" className="journal-discovery-link">
              <span className="journal-discovery-icon memories">
                <Images size={25} />
              </span>
              <div>
                <h3>Kỷ niệm của bạn</h3>
                <p>Xem lại những khoảnh khắc đã lưu.</p>
              </div>
              <ArrowRight size={19} />
            </Link>
            <Link to="/self/daily" className="journal-discovery-link">
              <span className="journal-discovery-icon insights">
                <BarChart3 size={25} />
              </span>
              <div>
                <h3>Nhìn lại tâm trạng</h3>
                <p>Điểm tâm trạng hằng ngày đã ghi trước đây.</p>
              </div>
              <ArrowRight size={19} />
            </Link>
          </div>
          <section className="journal-recent">
            <div className="journal-section-heading">
              <h2>Khoảnh khắc gần đây</h2>
              <Link to="/self/memories">
                Xem tất cả
                <ArrowRight size={16} />
              </Link>
            </div>
            <ErrorNotice error={recent.error} retry={recent.refresh} />
            {recent.loading && !recent.data ? (
              <p role="status">Đang tải khoảnh khắc…</p>
            ) : recent.data?.items.length ? (
              recent.data.items.map((item) => (
                <JournalEntryCard entry={item} key={item.id} />
              ))
            ) : (
              <p className="journal-empty-small">
                Những khoảnh khắc bạn lưu sẽ ở đây, để một ngày nhìn lại.
              </p>
            )}
          </section>
          <p className="journal-privacy-note">
            Nội dung chỉ hiển thị với tài khoản của bạn. Nhịp có thể đọc lời
            viết đã lưu khi bạn trò chuyện với Nhịp, và không đọc ảnh, ghi âm
            hay video. Nhật ký được giữ 90 ngày theo ngày của tài khoản.
          </p>
        </aside>
      </div>
    </div>
  );
}

export function JournalCompanion() {
  return (
    <div className="journal-page journal-companion-page">
      <JournalNav />
      <header className="journal-intro">
        <div>
          <h1 tabIndex={-1}>Nhịp đồng hành</h1>
          <p>Chậm một nhịp, nghe mình một chút.</p>
        </div>
        <BotAvatar id="nhip" size={96} />
      </header>
      <div className="journal-companion-intro">
        <p>
          Nhịp ở đây để lắng nghe và cùng bạn nhìn lại những khoảnh khắc trong
          nhật ký. Khi có dẫn chứng, bạn có thể mở lại ghi chép gốc.
        </p>
        <p>
          Nội dung của bạn vẫn riêng tư. Nhịp chỉ đọc nhật ký thuộc tài khoản
          này khi bạn trò chuyện với Nhịp.
        </p>
      </div>
      <section className="journal-companion-questions">
        <h2>Bạn muốn biết điều gì?</h2>
        {[
          "Tâm trạng của mình dạo này thế nào?",
          "Điều gì khiến mình vui nhất?",
          "Có chủ đề nào lặp lại không?",
          "Xem lại những khoảnh khắc đáng nhớ",
        ].map((question) => (
          <Link
            key={question}
            to={`/assistants/nhip?new=1&journalPrompt=${encodeURIComponent(question)}`}
          >
            <CalendarDays size={21} />
            <span>{question}</span>
            <ArrowRight size={19} />
          </Link>
        ))}
      </section>
      <section className="journal-prompts">
        <h2>Một gợi ý để viết</h2>
        <div>
          {writingPrompts.map((prompt, index) => (
            <Link to={`/self?prompt=${index}`} key={prompt}>
              <Lightbulb size={22} />
              <span>{prompt}</span>
              <ArrowRight size={17} />
            </Link>
          ))}
        </div>
      </section>
      <p className="journal-help">
        <Link to="/self/daily">Xem điểm tâm trạng đã ghi</Link>
      </p>
      <Link className="journal-companion-cta" to="/assistants/nhip?new=1">
        Nhắn cho Nhịp
        <ArrowRight size={20} />
      </Link>
    </div>
  );
}
import { useEffect, useMemo, useState } from "react";
