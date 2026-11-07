import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { LogOut, RotateCcw, SlidersHorizontal } from "lucide-react";
import { useDemoStore } from "../../app/store";
import {
  Badge,
  Button,
  Field,
  Modal,
  Notice,
  PageHeader,
} from "../../components/ui";
import type { AgeBand } from "../../types";
export function SettingsPage() {
  const user = useDemoStore((s) => s.user);
  const updateUser = useDemoStore((s) => s.updateUser);
  const preferences = useDemoStore((s) => s.preferences);
  const setPreferences = useDemoStore((s) => s.setPreferences);
  const notify = useDemoStore((s) => s.notify);
  const logout = useDemoStore((s) => s.logout);
  const reset = useDemoStore((s) => s.reset);
  const failNextSave = useDemoStore((s) => s.failNextSave);
  const setFailNextSave = useDemoStore((s) => s.setFailNextSave);
  const [nickname, setNickname] = useState(user?.nickname ?? "");
  const [age, setAge] = useState<AgeBand>(user?.ageBand ?? "11–13");
  const [confirm, setConfirm] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();
  return (
    <>
      <PageHeader
        title="Hồ sơ & cài đặt"
        description="Điều chỉnh không gian demo cho phù hợp với bạn."
        back="/support"
      />
      <div className="settings-form">
        <Badge tone="gray">Tài khoản minh họa</Badge>
        <form
          className="settings-section"
          onSubmit={(e) => {
            e.preventDefault();
            if (nickname.trim().length < 2) {
              setError("Bí danh cần ít nhất 2 ký tự.");
              return;
            }
            updateUser({ nickname: nickname.trim(), ageBand: age });
            setError("");
            notify("Đã cập nhật bí danh và nhóm tuổi demo.");
          }}
        >
          <h2>Thông tin của bạn</h2>
          <Field
            label="Bí danh"
            value={nickname}
            onChange={(e) => setNickname(e.target.value)}
            error={error}
            maxLength={32}
          />
          <div className="field">
            <label htmlFor="setting-age">Nhóm tuổi</label>
            <select
              id="setting-age"
              value={age}
              onChange={(e) => setAge(e.target.value as AgeBand)}
            >
              <option>11–13</option>
              <option>14–17</option>
            </select>
          </div>
          <Button type="submit">Lưu thay đổi</Button>
        </form>
        <section className="settings-section">
          <h2>Nhịp trải nghiệm</h2>
          <label className="toggle-label">
            <input
              type="checkbox"
              checked={preferences.reducedMotion}
              onChange={(e) =>
                setPreferences({ reducedMotion: e.target.checked })
              }
            />
            <span>Giảm chuyển động</span>
          </label>
          <p className="caption">
            Ứng dụng cũng tôn trọng cài đặt giảm chuyển động của thiết bị.
          </p>
        </section>
        <section className="settings-section">
          <h2>Dữ liệu demo trên thiết bị</h2>
          <Notice>
            Chỉ dùng thông tin hư cấu. Thay đổi được lưu trong trình duyệt này.
            Không có dữ liệu nào được gửi ra ngoài; chế độ bí danh không phải ẩn
            danh tuyệt đối.
          </Notice>
          <div className="actions" style={{ marginTop: 20 }}>
            <Button variant="secondary" onClick={() => setConfirm(true)}>
              <RotateCcw size={17} />
              Khôi phục dữ liệu mẫu
            </Button>
            <Button
              variant="ghost"
              onClick={() => {
                logout();
                navigate("/auth");
              }}
            >
              <LogOut size={17} />
              Đăng xuất demo
            </Button>
          </div>
        </section>
        <section className="settings-section">
          <h2>
            <SlidersHorizontal size={20} /> Điều khiển bản demo
          </h2>
          <label className="toggle-label">
            <input
              type="checkbox"
              checked={failNextSave}
              onChange={(e) => setFailNextSave(e.target.checked)}
            />
            <span>Mô phỏng lỗi ở lần lưu tiếp theo</span>
          </label>
          <p className="caption">
            Lỗi chỉ xảy ra một lần. Bạn có thể thử lưu lại và giữ nguyên nội
            dung nhập.
          </p>
          <div className="actions" style={{ marginTop: 18 }}>
            <Link to="/demo/school" className="button secondary">
              Xem demo dành cho nhà trường
            </Link>
            <Link
              to="/support/knowledge?search=khong-co-ket-qua"
              className="button ghost"
            >
              Thử tìm kiếm không có kết quả
            </Link>
          </div>
        </section>
      </div>
      <Modal
        open={confirm}
        onClose={() => setConfirm(false)}
        title="Khôi phục dữ liệu mẫu?"
      >
        <p>
          Mọi thay đổi trong demo trên trình duyệt sẽ bị xóa, tài khoản demo
          được đăng xuất và dữ liệu mẫu được khôi phục. Không có tài khoản thật
          nào bị ảnh hưởng.
        </p>
        <div className="actions end">
          <Button variant="secondary" onClick={() => setConfirm(false)}>
            Hủy
          </Button>
          <Button
            variant="danger"
            onClick={() => {
              reset();
              navigate("/welcome/1");
            }}
          >
            Khôi phục
          </Button>
        </div>
      </Modal>
    </>
  );
}
