import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  BookOpen,
  FilePenLine,
  Heart,
  HandHeart,
  MessagesSquare,
  Mic,
  Sun,
  Sparkles,
} from "lucide-react";
import { useWorkspaceStore } from "../../app/store";
import { getServices } from "../../services/composition";
import {
  Badge,
  Button,
  EmptyState,
  Progress,
  SectionHeading,
  Notice,
} from "../../components/ui";
import { FlowerArt } from "../../components/layout/Brand";
import { formatDate } from "../../lib/utils";
const actions = [
  {
    to: "/cases/new",
    title: "Ghi lại sự việc",
    text: "Lưu điều bạn muốn nhớ",
    Icon: FilePenLine,
  },
  {
    to: "/ai/roleplay",
    title: "Luyện cách nói",
    text: "Tự tin hơn từng chút",
    Icon: Mic,
  },
  {
    to: "/support/find-help",
    title: "Tìm người hỗ trợ",
    text: "Chọn người bạn tin tưởng",
    Icon: HandHeart,
  },
  {
    to: "/support/knowledge",
    title: "Góc kiến thức",
    text: "Hiểu để biết cách làm",
    Icon: BookOpen,
  },
];
const statusLabels: Record<string, string> = {
  active: "Đang ghi nhận",
  draft: "Bản nháp",
  monitoring: "Đang theo dõi",
  closed: "Đã tự đóng",
};
export function HomePage() {
  const user = useWorkspaceStore((s) => s.user);
  const demo = useWorkspaceStore((s) => s.workspace.kind === "demo");
  const [pendingItem, setPendingItem] = useState("");
  const [error, setError] = useState("");
  const cases = useWorkspaceStore((s) => s.cases)
    .filter((c) => c.ownerId === user?.id)
    .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  const plans = useWorkspaceStore((s) => s.plans);
  const notify = useWorkspaceStore((s) => s.notify);
  const plan =
    plans.find(
      (p) => cases.some((c) => c.id === p.caseId) && p.status !== "completed",
    ) ?? plans.find((p) => cases.some((c) => c.id === p.caseId));
  const done = plan?.items.filter((i) => i.status === "done").length ?? 0;
  return (
    <>
      <div className="home-welcome">
        <div>
          <h1>
            Chào {user?.nickname}, mình ở đây.{" "}
            <Sun
              size={24}
              color="#a48743"
              style={{ verticalAlign: "middle" }}
            />
          </h1>
          <p>Hôm nay, bạn muốn bắt đầu từ đâu?</p>
        </div>
        <span className="date-note">
          Một ngày mới,
          <br />
          một bước nhỏ.
        </span>
      </div>
      <section className="home-hero">
        <div className="hero-copy">
          <h2>
            Bạn có thể kể
            <br />
            từng chút một.
          </h2>
          <p>
            Không cần tìm đúng lời ngay. Cùng MoodPrint hiểu điều đang khiến bạn
            bận tâm.
          </p>
          <Link to="/ai/chat" className="button primary">
            <MessagesSquare size={18} />
            Bắt đầu trò chuyện
            <ArrowRight size={16} />
          </Link>
        </div>
        <FlowerArt />
      </section>
      <div className="quick-actions">
        {actions.map(({ to, title, text, Icon }) => (
          <Link className="quick-action" to={to} key={to}>
            <span className="quick-icon">
              <Icon size={21} />
            </span>
            <strong>{title}</strong>
            <span>{text}</span>
          </Link>
        ))}
      </div>
      <div className="home-columns">
        <section>
          <SectionHeading title="Điều bạn đang ghi lại" to="/cases" />
          <div className="panel">
            {cases.length ? (
              cases.slice(0, 2).map((c) => (
                <Link className="home-case" to={`/cases/${c.id}`} key={c.id}>
                  <Badge tone={c.status === "monitoring" ? "blue" : "green"}>
                    {statusLabels[c.status]}
                  </Badge>
                  <h3>{c.title}</h3>
                  <p>{c.summary || "Bạn có thể bổ sung khi sẵn sàng."}</p>
                  <footer>
                    <span>Cập nhật {formatDate(c.updatedAt)}</span>
                    <ArrowRight size={17} />
                  </footer>
                </Link>
              ))
            ) : (
              <EmptyState
                title="Một nơi để ghi nhớ"
                description="Bạn có thể bắt đầu với một vài dòng, hoặc trò chuyện trước."
                action={
                  <Link to="/cases/new" className="button secondary">
                    Ghi lại sự việc
                  </Link>
                }
              />
            )}
          </div>
        </section>
        <section>
          <SectionHeading
            title="Bước nhỏ tiếp theo"
            to={plan ? `/cases/${plan.caseId}/plan` : "/cases"}
            label="Xem kế hoạch"
          />
          <div className="panel">
            {plan ? (
              <>
                <div className="heading-row">
                  <Sparkles size={22} />
                  <Badge tone="gray">
                    {plan.status === "paused"
                      ? "Đang tạm dừng"
                      : "Theo nhịp của bạn"}
                  </Badge>
                </div>
                <h3 className="home-plan-title">{plan.goal}</h3>
                {plan.items.slice(0, 3).map((item) => (
                  <label className="home-check" key={item.id}>
                    <input
                      type="checkbox"
                      checked={item.status === "done"}
                      disabled={plan.status === "paused" || !!pendingItem}
                      onChange={async () => {
                        setPendingItem(item.id);
                        setError("");
                        try {
                          await getServices().plans.setItemStatus(
                            plan.id,
                            item.id,
                            item.status === "done" ? "not_started" : "done",
                          );
                          notify(
                            demo
                              ? "Đã cập nhật bước trong kế hoạch demo."
                              : "Đã cập nhật bước trong kế hoạch.",
                          );
                        } catch (cause) {
                          setError(
                            cause instanceof Error
                              ? cause.message
                              : "Chưa cập nhật được bước. Hãy thử lại.",
                          );
                        } finally {
                          setPendingItem("");
                        }
                      }}
                    />
                    <span
                      style={{
                        textDecoration:
                          item.status === "done" ? "line-through" : undefined,
                      }}
                    >
                      {item.label}
                    </span>
                  </label>
                ))}
                <p className="plan-mini">
                  {done}/{plan.items.length} bước bạn đã ghi hoàn thành
                </p>
                <Progress value={done} max={plan.items.length} />
                {error && <Notice tone="error">{error}</Notice>}
              </>
            ) : (
              <>
                <h3>Khi bạn sẵn sàng</h3>
                <p
                  className="muted"
                  style={{ margin: "12px 0 18px", fontSize: 14 }}
                >
                  Kế hoạch trong hồ sơ giúp bạn chia việc thành những bước vừa
                  sức.
                </p>
                <Link to="/cases" className="button secondary">
                  Mở hồ sơ
                </Link>
              </>
            )}
          </div>
        </section>
      </div>
      <SectionHeading
        title="Một chút kiến thức, thêm tự tin"
        to="/support/knowledge"
        label="Khám phá"
      />
      <div className="grid-2">
        <Link className="learning-row" to="/support/knowledge?topic=online">
          <span className="learning-glyph">
            <MessagesSquare size={28} />
          </span>
          <div>
            <h3>Khi những tin nhắn làm bạn khó chịu</h3>
            <p>Nhận biết dấu hiệu · Hướng dẫn từng bước</p>
          </div>
          <ArrowRight size={18} style={{ marginLeft: "auto" }} />
        </Link>
        <Link
          className="learning-row"
          to="/support/knowledge?topic=communication"
        >
          <span className="learning-glyph">
            <Heart size={28} />
          </span>
          <div>
            <h3>Bắt đầu nói với một người tin tưởng</h3>
            <p>Chuẩn bị lời nói · Tìm người đồng hành</p>
          </div>
          <ArrowRight size={18} style={{ marginLeft: "auto" }} />
        </Link>
      </div>
      <div className="gentle-note">
        <Heart size={20} />
        <p>
          Bạn không cần làm mọi thứ hôm nay. Chọn một việc nhỏ cũng là một cách
          bắt đầu.
        </p>
        <Button
          variant="ghost"
          onClick={() =>
            notify(
              demo
                ? "Bạn có thể tạm dừng và quay lại bất cứ lúc nào. Dữ liệu demo đã lưu trên trình duyệt này."
                : "Bạn có thể tạm dừng và quay lại bất cứ lúc nào. Những thay đổi đã lưu được giữ trong tài khoản của bạn.",
            )
          }
          aria-label="Tìm hiểu về nhịp trải nghiệm của bạn"
        >
          Tìm hiểu
        </Button>
      </div>
    </>
  );
}
