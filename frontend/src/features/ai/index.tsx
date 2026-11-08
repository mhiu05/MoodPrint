import { Link, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  FileImage,
  MessageCircle,
  Mic,
  Sparkles,
} from "lucide-react";
import { useWorkspaceStore } from "../../app/store";
import {
  Badge,
  EmptyState,
  PageHeader,
  Notice,
  SectionHeading,
} from "../../components/ui";
import { AgentStatusOrb } from "../../animations/AgentStatusOrb";
import { startFixtureAnalysis } from "./analysis-workflow";
import "./ai.css";
export { ChatPage } from "./chat";
export { AnalysisPage } from "./analysis";
export { RoleplayPage } from "./roleplay";

export function AIHub() {
  const real = useWorkspaceStore((state) => state.workspace.kind === "real");
  const user = useWorkspaceStore((state) => state.user);
  const chats = useWorkspaceStore((state) => state.chats);
  const roleplays = useWorkspaceStore((state) => state.roleplays);
  const navigate = useNavigate();
  const mine = chats
    .filter((chat) => chat.ownerId === user?.id)
    .slice(-3)
    .reverse();
  const practice = roleplays
    .filter(
      (session) =>
        session.ownerId === user?.id && session.status !== "completed",
    )
    .at(-1);
  return (
    <div className="ai-feature stack">
      <PageHeader
        title="Có thể bắt đầu từ một câu."
        description="Kể từng chút một, hoặc thử trước điều bạn muốn nói."
        action={
          <div className="actions">
            <AgentStatusOrb state="idle" size={32} showLabel={false} />
            <Badge tone="lavender">AI mô phỏng</Badge>
          </div>
        }
      />
      {real && (
        <Notice>
          AI mô phỏng · Chat, phân tích ảnh và luyện nói chỉ lưu trên thiết bị
          này.
        </Notice>
      )}
      <div className="ai-entry-grid">
        <Link className="ai-entry ai-entry-chat" to="/ai/chat">
          <MessageCircle size={30} />
          <h2>Trò chuyện</h2>
          <p>Thử một tình huống mẫu, làm rõ điều đã biết và điều còn thiếu.</p>
          <span>
            Bắt đầu kể <ArrowRight size={18} />
          </span>
        </Link>
        <Link className="ai-entry ai-entry-practice" to="/ai/roleplay">
          <Mic size={30} />
          <h2>Luyện cách nói</h2>
          <p>Tập nói với giáo viên, phụ huynh hoặc người lớn bạn tin tưởng.</p>
          <span>
            Vào phòng luyện <ArrowRight size={18} />
          </span>
        </Link>
      </div>
      <section>
        <SectionHeading title="Bạn đang muốn nói về…" />
        <div className="chips">
          {[
            ["Tin nhắn làm mình lo", "SC-07"],
            ["Bị bỏ ra ngoài nhóm", "SC-03"],
            ["Không biết nói với ai", "SC-13"],
          ].map(([label, id]) => (
            <Link className="chip" key={id} to={`/ai/chat?scenario=${id}`}>
              {label}
              <ArrowRight size={15} />
            </Link>
          ))}
        </div>
      </section>
      <section className="ai-fixture-entry">
        <div>
          <FileImage size={24} />
          <div>
            <h3>Cùng xem 8 ảnh chụp mẫu</h3>
            <p>
              {real
                ? "Rà soát nguồn và thử xác nhận nội dung; ảnh mẫu không lưu vào hồ sơ thật."
                : "Rà soát nguồn, sửa nội dung và xác nhận trước khi tạo hồ sơ."}
            </p>
          </div>
        </div>
        <button
          className="button secondary"
          onClick={() =>
            navigate(`/ai/analysis/${startFixtureAnalysis("multi").id}`)
          }
        >
          Mở bộ ảnh hư cấu
          <ArrowRight size={17} />
        </button>
      </section>
      <section>
        <SectionHeading
          title="Cuộc trò chuyện gần đây"
          to="/ai/chat"
          label="Cuộc trò chuyện mới"
        />
        {mine.length ? (
          <div className="panel">
            {mine.map((chat) => (
              <Link
                className="ai-recent-row"
                key={chat.id}
                to={`/ai/chat/${chat.id}`}
              >
                <MessageCircle size={21} />
                <div>
                  <strong>{chat.title}</strong>
                  <small>
                    {chat.draft ? "Có bản nháp · " : ""}
                    {chat.messages.length} tin nhắn · tình huống mẫu
                  </small>
                </div>
                <ArrowRight size={18} />
              </Link>
            ))}
          </div>
        ) : (
          <EmptyState
            title="Một trang trò chuyện mới"
            description="Cuộc trò chuyện mẫu của bạn sẽ ở đây để bạn quay lại khi muốn."
          />
        )}
      </section>
      {practice && (
        <Link
          className="ai-resume"
          to={`/ai/roleplay/${practice.role}?session=${practice.id}`}
        >
          <Sparkles size={21} />
          <span>
            Tiếp tục buổi luyện đang{" "}
            {practice.status === "paused" ? "tạm dừng" : "làm dở"}
          </span>
          <ArrowRight size={18} />
        </Link>
      )}
      <p className="ai-demo-footnote">
        Nội dung dựng sẵn, chỉ lưu trên trình duyệt này. Không có AI, OCR, ghi
        âm hoặc gửi thông tin thật.
      </p>
    </div>
  );
}
