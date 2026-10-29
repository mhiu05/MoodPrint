import { Suspense, lazy, useEffect, useState } from "react";
import type { ApiClient } from "../../api/client";
import type { SessionView } from "../../api/contracts";
import type { components } from "../../api/generated/schema";
import { BotAvatar, BrandMark } from "../../companions/Avatar";
import type { BotId } from "../../companions/registry";
import { Button, cx } from "../../components/UI";
import "./landing.css";

type Experience = components["schemas"]["PublicExperience"];
const GuestEntry = lazy(() =>
  import("../guest/GuestEntry").then((module) => ({ default: module.GuestEntry })),
);

const ASSISTANTS: { id: BotId; name: string; line: string }[] = [
  { id: "may", name: "Mây", line: "Có một điều muốn kể? Mây ở đây để lắng nghe." },
  { id: "guong", name: "Gương", line: "Khám phá sở thích và điều bạn coi trọng." },
  { id: "nhip", name: "Nhịp", line: "Nhìn lại cảm xúc, chọn một thói quen nhỏ." },
  { id: "rure", name: "Rủ Rê", line: "Cùng giải đố, học hỏi hoặc thử điều mới." },
  { id: "caunoi", name: "Cầu Nối", line: "Tập mở lời và tìm điểm chung để kết nối." },
];

const FAQ = [
  [
    "Có cần tạo tài khoản không?",
    "Bạn có thể dùng thử 2 giờ mà không cần email. Tạo tài khoản khi muốn tiếp tục sử dụng lâu dài.",
  ],
  [
    "Hết 2 giờ thì sao?",
    "Lượt dùng thử kết thúc và dữ liệu của lượt này không mở lại được. Bạn có thể bắt đầu lượt mới với dữ liệu trống.",
  ],
  [
    "Người khác có thấy cuộc trò chuyện của tôi không?",
    "Cuộc trò chuyện với trợ lý và nhật ký không được dùng làm hồ sơ tìm bạn. Bạn chủ động chọn thông tin muốn chia sẻ.",
  ],
  [
    "Dùng thử có tìm bạn được không?",
    "Tìm bạn và nhắn tin cần tài khoản, xác nhận đủ 18 tuổi và quyền chia sẻ do bạn bật.",
  ],
  [
    "Trợ lý có thay chuyên gia chăm sóc sức khỏe không?",
    "MoodPrint hỗ trợ trò chuyện và tự nhìn lại; không thay thế tư vấn hay điều trị chuyên môn.",
  ],
] as const;

/**
 * Public welcome page. Everything useful renders without the API; reading the readiness endpoint
 * and an existing session is optional and never creates an identity.
 */
export function LandingPage({ api }: { api: ApiClient }) {
  // undefined = still checking, null = readiness unreachable (the page itself stays fully usable).
  const [experience, setExperience] = useState<Experience | null | undefined>(undefined);
  const [known, setKnown] = useState<SessionView | null>(null);
  const [entryOpen, setEntryOpen] = useState(false);
  const [offline, setOffline] = useState(() => !navigator.onLine);

  useEffect(() => {
    const controller = new AbortController();
    api
      .request<Experience>("/public/experience", { signal: controller.signal })
      .then((value) => !controller.signal.aborted && setExperience(value))
      .catch(() => !controller.signal.aborted && setExperience(null));
    api
      .request<SessionView>("/session", { signal: controller.signal })
      .then((value) => !controller.signal.aborted && setKnown(value))
      .catch(() => undefined);
    const toggle = () => setOffline(!navigator.onLine);
    window.addEventListener("online", toggle);
    window.addEventListener("offline", toggle);
    return () => {
      controller.abort();
      window.removeEventListener("online", toggle);
      window.removeEventListener("offline", toggle);
    };
  }, [api]);

  const ready = Boolean(experience?.guestAvailable && experience.captchaSiteKey);
  const ctaNote = offline
    ? "Bạn đang ngoại tuyến."
    : experience === undefined
      ? "Đang kiểm tra…"
      : ready
        ? "Không cần email để dùng thử. Không gian riêng dành cho người từ 16 tuổi."
        : "Chưa thể bắt đầu lượt dùng thử. Thử lại sau.";

  return (
    <div className="landing">
      <a className={cx.skipLink} href="#noi-dung">
        Đến nội dung chính
      </a>
      <header className="landing-header">
        <a className="landing-brand" href="/" aria-label="MoodPrint">
          <BrandMark />
          <span>MoodPrint</span>
        </a>
        <nav aria-label="Trang giới thiệu">
          <a href="#tro-ly">Trợ lý</a>
          <a href="#cam-xuc">Cảm xúc</a>
          <a href="#quyen-rieng-tu">Quyền riêng tư</a>
          <a href="#cau-hoi">Câu hỏi</a>
        </nav>
        <a className={`${cx.button} ${cx.secondary}`} href="/#/login">
          Đăng nhập / Đăng ký
        </a>
      </header>

      <main id="noi-dung" tabIndex={-1}>
        <section className="landing-hero" aria-labelledby="hero">
          <h1 id="hero">Hiểu mình hơn, kết nối chân thành hơn.</h1>
          <p>
            Ghi lại cảm xúc, trò chuyện cùng 5 trợ lý và khám phá điều quan trọng với bạn.
          </p>
          <div className="landing-actions">
            {known ? (
              <a className={`${cx.button} ${cx.primary}`} href="/#/assistants">
                Tiếp tục sử dụng
              </a>
            ) : (
              <Button className="landing-trial" disabled={!ready || offline} onClick={() => setEntryOpen(true)}>
                Dùng thử 2 giờ
              </Button>
            )}
            <a className={`${cx.button} ${cx.secondary}`} href="/#/login?mode=signup">
              Tạo tài khoản
            </a>
          </div>
          <p className={cx.footnote} role="status">
            {known ? "Bạn đã có một phiên đang mở." : ctaNote}
          </p>
        </section>

        <section aria-labelledby="vi-du">
          <h2 id="vi-du">Bắt đầu bằng một điều bạn đang nghĩ</h2>
          <ul className="landing-examples">
            <li>
              <strong>Bắt đầu bằng một điều bạn đang nghĩ.</strong> Chọn một gợi ý hoặc tự viết, rồi trò
              chuyện với trợ lý.
            </li>
            <li>
              <strong>Ghi lại cảm xúc theo nhịp của bạn.</strong> Một dấu ghi nhỏ mỗi ngày, ghi chú là tùy
              chọn.
            </li>
            <li>
              <strong>Bạn chọn điều trợ lý được ghi nhớ.</strong> Trợ lý chỉ đề xuất; bạn duyệt hoặc bỏ qua.
            </li>
          </ul>
        </section>

        <section id="tro-ly" aria-labelledby="tro-ly-tieu-de">
          <h2 id="tro-ly-tieu-de">Năm trợ lý, năm cách đồng hành</h2>
          <ul className="landing-assistants">
            {ASSISTANTS.map((bot) => (
              <li key={bot.id}>
                <BotAvatar id={bot.id} size={48} />
                <div>
                  <h3>{bot.name}</h3>
                  <p>{bot.line}</p>
                </div>
              </li>
            ))}
          </ul>
          <p className={cx.footnote}>
            Bản dùng thử có thể trò chuyện với Cầu Nối nhưng không tìm hay nhắn tin cho người thật. Rủ Rê
            hỗ trợ trò chơi và học hỏi ngay trong cuộc trò chuyện.
          </p>
        </section>

        <section id="cam-xuc" aria-labelledby="cam-xuc-tieu-de">
          <h2 id="cam-xuc-tieu-de">Nhật ký cảm xúc</h2>
          <p>Hôm nay bạn thấy thế nào? Một dấu ghi nhỏ để nhìn lại chính mình.</p>
        </section>

        <section aria-labelledby="ket-noi">
          <h2 id="ket-noi">Kết nối khi bạn sẵn sàng.</h2>
          <p>
            Tìm bạn và nhắn tin dành cho người từ 18 tuổi có tài khoản. Bạn chủ động chọn thông tin chia sẻ.
          </p>
        </section>

        <section id="quyen-rieng-tu" aria-labelledby="rieng-tu">
          <h2 id="rieng-tu">Dùng thử trong 2 giờ</h2>
          <p>
            Khi hết giờ, bạn không thể mở lại dữ liệu của lượt này. MoodPrint xóa dữ liệu khỏi hệ thống
            đang hoạt động; bản sao lưu và dịch vụ AI có thể giữ dữ liệu theo chính sách riêng của họ.
          </p>
        </section>

        <section id="cau-hoi" aria-labelledby="faq">
          <h2 id="faq">Câu hỏi thường gặp</h2>
          {FAQ.map(([question, answer]) => (
            <details key={question}>
              <summary>{question}</summary>
              <p>{answer}</p>
            </details>
          ))}
        </section>
      </main>

      <footer className="landing-footer">
        <p>
          Có điều gì chưa thuận tiện? <a href="/#/feedback">Góp ý cho MoodPrint</a>.
        </p>
        <Button className="landing-trial" disabled={!ready || offline || Boolean(known)} onClick={() => setEntryOpen(true)}>
          Dùng thử 2 giờ
        </Button>
      </footer>

      {entryOpen && experience?.captchaSiteKey ? (
        <Suspense fallback={<p role="status">Đang mở…</p>}>
          <GuestEntry
            api={api}
            siteKey={experience.captchaSiteKey}
            onClose={() => setEntryOpen(false)}
            onStarted={() => {
              setEntryOpen(false);
              window.location.hash = "#/assistants";
            }}
          />
        </Suspense>
      ) : null}
    </div>
  );
}
