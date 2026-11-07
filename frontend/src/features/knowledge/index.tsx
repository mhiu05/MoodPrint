import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  Bookmark,
  BookOpen,
  Check,
  CheckCircle2,
  Clock3,
  ExternalLink,
  Search,
  Sparkles,
} from "lucide-react";
import { useWorkspaceStore } from "../../app/store";
import {
  Badge,
  Button,
  EmptyState,
  LinkButton,
  Notice,
  PageHeader,
  Skeleton,
} from "../../components/ui";
import {
  filterKnowledge,
  formatLabels,
  knowledgeTopics,
} from "../../mocks/data/knowledge";
import { knowledgeSources } from "../../mocks/data/sources";
import { getServices } from "../../services/composition";
import type { KnowledgeArticle } from "../../types";
import "./knowledge.css";

const reviewDate = (date: string) =>
  new Date(`${date}T12:00:00`).toLocaleDateString("vi-VN");
function useArticleActions(id: string) {
  const [pending, setPending] = useState<string[]>([]);
  const [error, setError] = useState("");
  async function write(action: "toggleBookmark" | "markRead") {
    if (pending.includes(action)) return;
    setPending((current) => [...current, action]);
    setError("");
    try {
      await getServices().knowledgeState[action](id);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Chưa lưu được. Hãy thử lại.",
      );
    } finally {
      setPending((current) => current.filter((item) => item !== action));
    }
  }
  return {
    bookmarkBusy: pending.includes("toggleBookmark"),
    readBusy: pending.includes("markRead"),
    error,
    toggleBookmark: () => write("toggleBookmark"),
    markRead: () => write("markRead"),
  };
}
function KnowledgeRow({ article }: { article: KnowledgeArticle }) {
  const saved = useWorkspaceStore((s) => s.bookmarks.includes(article.id));
  const read = useWorkspaceStore((s) => s.readIds.includes(article.id));
  const { bookmarkBusy, error, toggleBookmark } = useArticleActions(article.id);
  return (
    <article className="knowledge-row">
      <div className={`knowledge-format ${article.format}`}>
        <BookOpen size={22} />
      </div>
      <div className="knowledge-row-copy">
        <div className="knowledge-meta">
          <span>{article.topics[0]}</span>
          <span>·</span>
          <span>{formatLabels[article.format]}</span>
          {read && (
            <span className="knowledge-read">
              <Check size={13} />
              Đã đọc
            </span>
          )}
        </div>
        {error && <Notice tone="error">{error}</Notice>}
        <h3>
          <Link to={`/knowledge/${article.slug}`}>{article.title}</Link>
        </h3>
        <p>{article.summary}</p>
        <div className="knowledge-meta">
          <Clock3 size={13} />
          {article.readMinutes} phút đọc<span>·</span>11–17 tuổi
        </div>
      </div>
      <Button
        variant="ghost"
        aria-label={`${saved ? "Bỏ lưu" : "Lưu"}: ${article.title}`}
        aria-pressed={saved}
        disabled={bookmarkBusy}
        onClick={toggleBookmark}
      >
        <Bookmark size={18} fill={saved ? "currentColor" : "none"} />
      </Button>
    </article>
  );
}

export function KnowledgeHub() {
  const [params, setParams] = useSearchParams();
  const query = params.get("search") || "";
  const requestedTopic = params.get("topic") || "";
  const topicAliases: Record<string, string> = {
    online: "Online",
    communication: "Nhờ hỗ trợ",
    "Trực tuyến": "Online",
    "Giao tiếp": "Nhờ hỗ trợ",
  };
  const topic =
    topicAliases[requestedTopic] ||
    (knowledgeTopics.includes(requestedTopic) ? requestedTopic : "");
  function setParam(name: string, value: string) {
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        if (value) next.set(name, value);
        else next.delete(name);
        return next;
      },
      { replace: true },
    );
  }
  const setQuery = (value: string) => setParam("search", value);
  const setTopic = (value: string) => setParam("topic", value);
  const [age, setAge] = useState("");
  const [format, setFormat] = useState("");
  const [collection, setCollection] = useState("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const bookmarks = useWorkspaceStore((s) => s.bookmarks);
  const readIds = useWorkspaceStore((s) => s.readIds);
  const results = filterKnowledge(getServices().knowledgeCatalog.list(), {
    query,
    topic,
    age,
    format,
  }).filter((a) =>
    collection === "saved"
      ? bookmarks.includes(a.id)
      : collection === "read"
        ? readIds.includes(a.id)
        : collection === "unread"
          ? !readIds.includes(a.id)
          : true,
  );
  const reset = () => {
    setParams({}, { replace: true });
    setAge("");
    setFormat("");
    setCollection("all");
  };
  async function reload() {
    setLoading(true);
    setError("");
    try {
      await getServices().run(() => getServices().knowledgeCatalog.list());
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Chưa tải được thư viện mẫu. Hãy thử lại.",
      );
    } finally {
      setLoading(false);
    }
  }
  return (
    <div className="knowledge-page stack">
      <PageHeader
        title="Hiểu thêm, từng chút một"
        description="Không cần biết hết. Bắt đầu từ điều gần với câu chuyện của bạn."
        back="/support"
      />
      <section className="knowledge-intro">
        <div>
          <span className="knowledge-eyebrow">Thư viện MoodPrint</span>
          <h2>Một góc nhỏ để tìm câu trả lời.</h2>
          <p>
            Hướng dẫn dễ đọc, tình huống để thử và lời mở đầu khi bạn cần nhờ
            giúp.
          </p>
          <div className="knowledge-intro-facts">
            <span>
              <BookOpen size={16} />
              24 bài đọc
            </span>
            <span>
              <CheckCircle2 size={16} />
              15 hoạt động nhỏ
            </span>
          </div>
        </div>
        <div className="knowledge-book" aria-hidden="true">
          <span />
          <span />
          <BookOpen size={68} />
        </div>
      </section>
      <div className="knowledge-search">
        <Search size={20} />
        <input
          type="search"
          aria-label="Tìm trong thư viện"
          placeholder="Thử “bị cô lập”, “nhờ giáo viên”…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      <div className="knowledge-layout">
        <aside className="knowledge-filters">
          <h2>Tìm điều phù hợp</h2>
          <div className="field">
            <label htmlFor="knowledge-topic">Chủ đề</label>
            <select
              id="knowledge-topic"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
            >
              <option value="">Mọi chủ đề</option>
              {knowledgeTopics.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="knowledge-age">Độ tuổi</label>
            <select
              id="knowledge-age"
              value={age}
              onChange={(e) => setAge(e.target.value)}
            >
              <option value="">11–17 tuổi</option>
              <option>11–13</option>
              <option>14–17</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="knowledge-format">Cách học</label>
            <select
              id="knowledge-format"
              value={format}
              onChange={(e) => setFormat(e.target.value)}
            >
              <option value="">Mọi định dạng</option>
              {Object.entries(formatLabels).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <p className="knowledge-filter-note">
            Chọn một bài là đủ cho hôm nay. Bạn có thể lưu lại để đọc khi thấy
            sẵn sàng.
          </p>
          <Button variant="ghost" onClick={reset}>
            Xóa bộ lọc
          </Button>
        </aside>
        <section className="knowledge-results" aria-label="Bài viết">
          <div className="knowledge-tabs" role="group" aria-label="Bộ sưu tập">
            {[
              ["all", "Tất cả"],
              ["saved", `Đã lưu (${bookmarks.length})`],
              ["read", "Đã đọc"],
              ["unread", "Chưa đọc"],
            ].map(([key, label]) => (
              <button
                key={key}
                aria-pressed={collection === key}
                onClick={() => setCollection(key)}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="knowledge-result-count" aria-live="polite">
            <span>{results.length} bài phù hợp</span>
            <Button variant="ghost" disabled={loading} onClick={reload}>
              {loading ? "Đang tải…" : "Tải lại thư viện mẫu"}
            </Button>
          </div>
          {loading ? (
            <Skeleton />
          ) : error ? (
            <Notice tone="error">
              <p>{error}</p>
              <Button variant="secondary" onClick={reload}>
                Thử tải lại
              </Button>
            </Notice>
          ) : results.length ? (
            <div>
              {results.map((article) => (
                <KnowledgeRow key={article.id} article={article} />
              ))}
            </div>
          ) : (
            <EmptyState
              title="Chưa tìm thấy bài phù hợp"
              description="Thử từ ngắn hơn, bỏ dấu hoặc chọn một chủ đề khác."
            />
          )}
        </section>
      </div>
      <div className="knowledge-help">
        <Sparkles size={22} />
        <div>
          <h2>Muốn nói về điều vừa đọc?</h2>
          <p>AI Companion mô phỏng có thể giúp bạn thử cách kể câu chuyện.</p>
        </div>
        <LinkButton to="/ai/chat" variant="secondary">
          Mở trò chuyện
          <ArrowRight size={16} />
        </LinkButton>
      </div>
    </div>
  );
}

export function ArticlePage() {
  const { slug } = useParams();
  const article = getServices()
    .knowledgeCatalog.list()
    .find((a) => a.slug === slug);
  return article ? (
    <ArticleReading key={article.id} article={article} />
  ) : (
    <div className="stack">
      <PageHeader title="Chưa tìm thấy bài viết" back="/support/knowledge" />
      <EmptyState
        title="Bài này không có trong thư viện mẫu"
        description="Đường dẫn có thể đã thay đổi. Bạn vẫn có thể tìm một chủ đề gần với điều mình cần."
        action={<LinkButton to="/support/knowledge">Về thư viện</LinkButton>}
      />
    </div>
  );
}

function ArticleReading({ article }: { article: KnowledgeArticle }) {
  const saved = useWorkspaceStore((s) => s.bookmarks.includes(article.id));
  const read = useWorkspaceStore((s) => s.readIds.includes(article.id));
  const { bookmarkBusy, readBusy, error, toggleBookmark, markRead } =
    useArticleActions(article.id);
  const [choice, setChoice] = useState<number | null>(null);
  const [quizChoice, setQuizChoice] = useState<number | null>(null);
  const related = getServices()
    .knowledgeCatalog.list()
    .filter(
      (a) =>
        a.id !== article.id &&
        (a.topics.some((t) => article.topics.includes(t)) || a.id === "KB-13"),
    )
    .slice(0, 3);
  const sources = knowledgeSources.filter((source) =>
    article.sourceIds.includes(source.id),
  );
  const aiQuery = new URLSearchParams({
    articleId: article.id,
    articleSlug: article.slug,
    sourceIds: article.sourceIds.join(","),
  });
  return (
    <div className="knowledge-reading stack">
      <PageHeader title={article.title} back="/support/knowledge" />
      <div className="knowledge-article-meta">
        <Badge tone="peach">{article.topics[0]}</Badge>
        <span>
          {formatLabels[article.format]} · {article.readMinutes} phút ·{" "}
          {article.ageBands.join(" / ")} tuổi
        </span>
      </div>
      <p className="knowledge-deck">{article.summary}</p>
      <div className="knowledge-article-actions">
        <Button
          variant="secondary"
          disabled={bookmarkBusy}
          onClick={toggleBookmark}
          aria-pressed={saved}
        >
          <Bookmark size={17} fill={saved ? "currentColor" : "none"} />
          {saved ? "Đã lưu bài viết" : "Lưu bài viết"}
        </Button>
        <span className="muted">
          Rà soát {reviewDate(article.lastReviewed)}
        </span>
      </div>
      {error && <Notice tone="error">{error}</Notice>}
      <div className="knowledge-summary">
        <strong>Trong 30 giây</strong>
        <p>{article.sections[0].body}</p>
      </div>
      <article className="knowledge-prose">
        {article.sections.slice(1).map((section, i) => (
          <section key={section.title}>
            <span className="knowledge-section-number">
              {String(i + 1).padStart(2, "0")}
            </span>
            <div>
              <h2>{section.title}</h2>
              <p>{section.body}</p>
            </div>
          </section>
        ))}
      </article>
      {article.scenario && (
        <section
          className="knowledge-activity"
          aria-label="Tình huống tương tác"
        >
          <Badge tone="lavender">Thử một lựa chọn</Badge>
          <p className="muted">
            Tình huống giả lập do MoodPrint biên tập. Bạn có thể thử lại, không
            chấm điểm con người.
          </p>
          <h2>{article.scenario.question}</h2>
          <div className="stack">
            {article.scenario.options.map((option, i) => (
              <button
                className="knowledge-option"
                key={option.label}
                aria-pressed={choice === i}
                onClick={() => setChoice(i)}
              >
                <span>{String.fromCharCode(65 + i)}</span>
                {option.label}
                {choice === i && <Check size={18} />}
              </button>
            ))}
          </div>
          {choice !== null && (
            <div className="knowledge-feedback" role="status">
              <strong>
                {article.scenario.options[choice].helpful
                  ? "Một lựa chọn bạn có thể cân nhắc"
                  : "Hãy thử nhìn thêm một góc khác"}
              </strong>
              <p>{article.scenario.options[choice].feedback}</p>
              <Button variant="ghost" onClick={() => setChoice(null)}>
                Chọn lại
              </Button>
            </div>
          )}
        </section>
      )}
      {article.quiz && (
        <section className="knowledge-activity" aria-label="Câu hỏi tương tác">
          <Badge tone="lavender">Dừng một nhịp, thử nghĩ</Badge>
          <p className="muted">
            Câu hỏi do MoodPrint biên tập để học qua ví dụ.
          </p>
          <h2>{article.quiz.question}</h2>
          <div className="stack">
            {article.quiz.options.map((option, i) => (
              <button
                className="knowledge-option"
                key={option}
                aria-pressed={quizChoice === i}
                onClick={() => setQuizChoice(i)}
              >
                <span>{String.fromCharCode(65 + i)}</span>
                {option}
              </button>
            ))}
          </div>
          {quizChoice !== null && (
            <div className="knowledge-feedback" role="status">
              <strong>
                {quizChoice === article.quiz.answer
                  ? "Bạn đã nhận ra bước hữu ích"
                  : "Cùng xem lại lựa chọn này"}
              </strong>
              <p>{article.quiz.explanation}</p>
              {quizChoice !== article.quiz.answer && (
                <p>Gợi ý: {article.quiz.options[article.quiz.answer]}</p>
              )}
              <Button variant="ghost" onClick={() => setQuizChoice(null)}>
                Thử lại
              </Button>
            </div>
          )}
        </section>
      )}
      <section className="knowledge-source-section">
        <h2>Nguồn để bạn đọc thêm</h2>
        <p>{article.applicability}</p>
        {sources.map((source) => (
          <div className="knowledge-source" key={source.id}>
            <strong>{source.publisher}</strong>
            <a href={source.url} target="_blank" rel="noreferrer">
              {source.title}
              <ExternalLink size={14} />
              <span className="sr-only"> (mở trang ngoài)</span>
            </a>
            <p>{source.applicability}</p>
            <small>Kiểm tra đường dẫn: {reviewDate(source.checkedAt)}</small>
            <details>
              <summary>Nếu liên kết không mở được</summary>
              <p>Bạn có thể sao chép địa chỉ và tự mở trong trình duyệt:</p>
              <code>{source.url}</code>
            </details>
          </div>
        ))}
      </section>
      <div className="actions">
        <Button
          variant={read ? "secondary" : "primary"}
          disabled={readBusy}
          onClick={markRead}
        >
          <CheckCircle2 size={18} />
          {read ? "Đã đọc bài này" : "Đánh dấu đã đọc"}
        </Button>
        <LinkButton variant="secondary" to={`/ai/chat?${aiQuery.toString()}`}>
          <Sparkles size={17} />
          Hỏi AI về bài này
        </LinkButton>
      </div>
      <p className="muted">
        AI là mô phỏng. Nếu bạn cần giúp trực tiếp,{" "}
        <Link to="/support/urgent">mở Hỗ trợ ngay</Link>.
      </p>
      <section>
        <h2>Đọc tiếp nếu bạn muốn</h2>
        {related.map((a) => (
          <KnowledgeRow key={a.id} article={a} />
        ))}
      </section>
    </div>
  );
}
