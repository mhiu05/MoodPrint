import { Link, Navigate, useParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, ShieldCheck } from "lucide-react";
import { useDemoStore } from "../../app/store";
import { Brand, FlowerArt } from "../../components/layout/Brand";
import { LinkButton } from "../../components/ui";
import { PageMotion } from "../../animations/PageMotion";
import "./entry.css";
const steps = [
  {
    title: "Có những chuyện thật khó để nói ra.",
    body: "Nếu chuyện ở trường hoặc trên mạng đang làm bạn bận tâm, bạn có thể bắt đầu ở đây. Từng chút một, theo cách của bạn.",
  },
  {
    title: "Một nơi để kể, một chút để nhẹ lòng.",
    body: "Cùng AI Companion mô phỏng làm rõ điều đã xảy ra. Bạn có thể bỏ qua câu hỏi hoặc dừng lại bất cứ lúc nào.",
  },
  {
    title: "Ghi lại hôm nay. Để hiểu hơn ngày mai.",
    body: "Giữ những điều bạn nhớ trong hồ sơ của mình. Xem lại diễn biến và chọn một bước nhỏ bạn thấy sẵn sàng.",
  },
  {
    title: "Luyện cách nói. Tìm người đồng hành.",
    body: "Thử một cuộc trò chuyện với giáo viên hoặc phụ huynh mô phỏng. Chuẩn bị lời nhắn cho một người bạn tin tưởng.",
  },
];
export function WelcomePage() {
  const user = useDemoStore((s) => s.user);
  const { step } = useParams();
  const number = Math.min(4, Math.max(1, Number(step) || 1));
  const data = steps[number - 1];
  if (user) return <Navigate to="/home" replace />;
  return (
    <main className="welcome-canvas">
      <header className="welcome-top">
        <Brand to="/welcome/1" />
        <Link to="/auth" className="button ghost">
          Bỏ qua
        </Link>
      </header>
      <section
        className="welcome-story"
        aria-label={`Giới thiệu, bước ${number} trong 4`}
      >
        <div className="welcome-art">
          <FlowerArt />
        </div>
        <PageMotion key={number}>
          <h1>{data.title}</h1>
          <p className="muted">{data.body}</p>
        </PageMotion>
        <div
          className="welcome-dots"
          aria-label={`Trang ${number} trong 4 trang`}
        >
          {steps.map((_, i) => (
            <span
              key={i}
              aria-current={i + 1 === number ? "step" : undefined}
              className={i + 1 === number ? "active" : ""}
            />
          ))}
        </div>
      </section>
      <footer className="welcome-actions">
        <div>
          {number > 1 ? (
            <LinkButton to={`/welcome/${number - 1}`} variant="ghost">
              <ArrowLeft size={18} />
              Quay lại
            </LinkButton>
          ) : (
            <LinkButton to="/support/urgent" variant="ghost">
              Cần hỗ trợ?
            </LinkButton>
          )}
          <LinkButton to={number === 4 ? "/auth" : `/welcome/${number + 1}`}>
            {number === 4 ? "Bắt đầu" : "Tiếp tục"}
            <ArrowRight size={18} />
          </LinkButton>
        </div>
        <small>
          <ShieldCheck size={15} />
          Prototype chỉ dùng dữ liệu giả lập, không gửi thông tin ra ngoài.
        </small>
      </footer>
    </main>
  );
}
