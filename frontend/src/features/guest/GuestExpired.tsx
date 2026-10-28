import "./guest.css";
import { useEffect, useRef } from "react";
import { Brand, Button, cx } from "../../components/UI";

/** Content-free end screen: no conversation, journal or identifier is shown or restorable. */
export function GuestExpired({
  reason,
  onNewTrial,
  onRegister,
}: {
  reason: "expired" | "ended";
  onNewTrial: () => void;
  onRegister: () => void;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => heading.current?.focus(), []);
  return (
    <main className="real-auth guest-ended" id="main">
      <Brand />
      <h1 ref={heading} tabIndex={-1}>
        Lượt dùng thử đã kết thúc
      </h1>
      <p role="status">
        {reason === "ended"
          ? "Yêu cầu kết thúc đã được ghi nhận. Dữ liệu đang được xử lý xóa."
          : "Dữ liệu của lượt này không thể mở lại. Hệ thống đang xóa dữ liệu khỏi các kho đang hoạt động."}
      </p>
      <p className={cx.footnote}>
        Bắt đầu lượt mới sẽ là một không gian hoàn toàn trống. Dữ liệu của lượt dùng thử không chuyển sang
        tài khoản.
      </p>
      <div className={cx.actions}>
        <Button onClick={onNewTrial}>Bắt đầu lượt dùng thử mới</Button>
        <Button variant="secondary" onClick={onRegister}>
          Tạo tài khoản
        </Button>
        <a className={`${cx.button} ${cx.secondary}`} href="/">
          Về trang giới thiệu
        </a>
      </div>
    </main>
  );
}
