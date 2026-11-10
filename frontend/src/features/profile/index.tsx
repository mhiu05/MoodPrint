import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { LogOut, RotateCcw, SlidersHorizontal } from "lucide-react";
import { useWorkspaceStore } from "../../app/store";
import { getServices } from "../../services/composition";
import { clearDemoData, logoutWorkspace } from "../../services/workspace";
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
  const user = useWorkspaceStore((s) => s.user);
  const real = useWorkspaceStore((s) => s.workspace.kind === "real");
  const preferences = useWorkspaceStore((s) => s.preferences);
  const notify = useWorkspaceStore((s) => s.notify);
  const failNextSave = useWorkspaceStore((s) => s.failNextSave);
  const setFailNextSave = useWorkspaceStore((s) => s.setFailNextSave);
  const [nickname, setNickname] = useState(user?.nickname ?? "");
  const [age, setAge] = useState<AgeBand>(user?.ageBand ?? "11–13");
  const [confirm, setConfirm] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [deleteStage, setDeleteStage] = useState(0);
  const [deleteText, setDeleteText] = useState("");
  const navigate = useNavigate();
  return (
    <>
      <PageHeader
        title="Hồ sơ & cài đặt"
        description={
          real
            ? "Điều chỉnh không gian của mình cho phù hợp với bạn."
            : "Điều chỉnh không gian demo cho phù hợp với bạn."
        }
        back="/support"
      />
      <div className="settings-form">
        <Badge tone="gray">
          {real ? "Tài khoản của bạn" : "Tài khoản minh họa"}
        </Badge>
        <form
          className="settings-section"
          onSubmit={(e) => {
            e.preventDefault();
            if (nickname.trim().length < 2) {
              setError("Bí danh cần ít nhất 2 ký tự.");
              return;
            }
            setBusy(true);
            setError("");
            void getServices()
              .profile.save({ nickname: nickname.trim(), ageBand: age })
              .then(() =>
                notify(
                  real
                    ? "Đã cập nhật bí danh và nhóm tuổi."
                    : "Đã cập nhật bí danh và nhóm tuổi demo.",
                ),
              )
              .catch((error) =>
                setError(
                  error instanceof Error
                    ? error.message
                    : "Chưa lưu được thay đổi. Hãy thử lại.",
                ),
              )
              .finally(() => setBusy(false));
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
          <Button type="submit" disabled={busy}>
            {busy ? "Đang lưu…" : "Lưu thay đổi"}
          </Button>
        </form>
        <section className="settings-section">
          <h2>Nhịp trải nghiệm</h2>
          <label className="toggle-label">
            <input
              type="checkbox"
              checked={preferences.reducedMotion}
              onChange={(e) =>
                void getServices()
                  .profile.save({ reducedMotion: e.target.checked })
                  .catch((error) =>
                    notify(
                      error instanceof Error
                        ? error.message
                        : "Chưa lưu được cài đặt.",
                    ),
                  )
              }
            />
            <span>Giảm chuyển động</span>
          </label>
          <p className="caption">
            Ứng dụng cũng tôn trọng cài đặt giảm chuyển động của thiết bị.
          </p>
        </section>
        <section className="settings-section">
          <h2>{real ? "Dữ liệu của bạn" : "Dữ liệu demo trên thiết bị"}</h2>
          <Notice>
            {real
              ? "Chỉ dùng thông tin hư cấu. Hồ sơ và tệp được lưu trong tài khoản của bạn. Nội dung AI mô phỏng nằm riêng trên thiết bị; bí danh không phải ẩn danh tuyệt đối."
              : "Chỉ dùng thông tin hư cấu. Thay đổi được lưu trong trình duyệt này. Không có dữ liệu nào được gửi ra ngoài; chế độ bí danh không phải ẩn danh tuyệt đối."}
          </Notice>
          <div className="actions" style={{ marginTop: 20 }}>
            {!real && (
              <Button variant="secondary" onClick={() => setConfirm(true)}>
                <RotateCcw size={17} />
                Khôi phục dữ liệu mẫu
              </Button>
            )}
            {real && (
              <>
                <Button
                  variant="secondary"
                  onClick={() => {
                    try {
                      clearDemoData();
                      notify("Đã xóa dữ liệu demo trên trình duyệt này.");
                    } catch (error) {
                      notify(
                        error instanceof Error
                          ? error.message
                          : "Chưa xóa được dữ liệu demo.",
                      );
                    }
                  }}
                >
                  Xóa dữ liệu demo trên trình duyệt này
                </Button>
                <Button variant="danger" onClick={() => setDeleteStage(1)}>
                  Xóa tài khoản
                </Button>
              </>
            )}
            <Button
              variant="ghost"
              onClick={() => {
                void logoutWorkspace()
                  .then(() => navigate("/auth"))
                  .catch((error) =>
                    notify(
                      error instanceof Error
                        ? error.message
                        : "Chưa đăng xuất được. Hãy thử lại.",
                    ),
                  );
              }}
            >
              <LogOut size={17} />
              {real ? "Đăng xuất" : "Đăng xuất demo"}
            </Button>
          </div>
        </section>
        {!real && (
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
        )}
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
              void getServices()
                .profile.remove()
                .then(() => navigate("/welcome/1"));
            }}
          >
            Khôi phục
          </Button>
        </div>
      </Modal>
      <Modal
        open={deleteStage > 0}
        onClose={() => {
          if (!busy) {
            setDeleteStage(0);
            setDeleteText("");
            setError("");
          }
        }}
        title={
          deleteStage === 1
            ? "Xóa tài khoản của bạn?"
            : "Xác nhận xóa vĩnh viễn"
        }
      >
        {deleteStage === 1 ? (
          <>
            <p>
              Hồ sơ, tệp bằng chứng và dữ liệu tài khoản sẽ bị xóa. Bạn có thể
              sao chép hoặc tải nội dung cần giữ trước khi tiếp tục.
            </p>
            <div className="actions end">
              <Button variant="secondary" onClick={() => setDeleteStage(0)}>
                Hủy
              </Button>
              <Button variant="danger" onClick={() => setDeleteStage(2)}>
                Tiếp tục xóa
              </Button>
            </div>
          </>
        ) : (
          <>
            <Field
              label="Nhập DELETE để xác nhận"
              value={deleteText}
              autoComplete="off"
              onChange={(event) => setDeleteText(event.target.value)}
            />
            {error && <Notice tone="error">{error}</Notice>}
            <div className="actions end">
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() => setDeleteStage(0)}
              >
                Hủy
              </Button>
              <Button
                variant="danger"
                disabled={busy || deleteText !== "DELETE"}
                onClick={() => {
                  setBusy(true);
                  setError("");
                  void getServices()
                    .profile.remove()
                    .then(() => logoutWorkspace())
                    .then(() => navigate("/auth", { replace: true }))
                    .catch((error) =>
                      setError(
                        error instanceof Error
                          ? error.message
                          : "Chưa xóa xong tài khoản. Hãy thử lại.",
                      ),
                    )
                    .finally(() => setBusy(false));
                }}
              >
                {busy ? "Đang xóa…" : "Xóa vĩnh viễn"}
              </Button>
            </div>
          </>
        )}
      </Modal>
    </>
  );
}
