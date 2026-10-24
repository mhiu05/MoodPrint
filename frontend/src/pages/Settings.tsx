import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ShieldCheck, SlidersHorizontal } from "lucide-react";
import type { Permission } from "../domain/types";
import { useDemo } from "../state/Provider";
import { safeExport } from "../state/reducer";
import {
  Badge,
  Button,
  cx,
  Dialog,
  Go,
  Intro,
  Tabs,
  useTab,
} from "../components/UI";
import { permissionCopy } from "./StartHome";
export function SettingsPage() {
  const tab = useTab(["privacy", "safety"], "privacy");
  return (
    <>
      <Intro
        eyebrow="Thoải mái là khi mình có lựa chọn"
        title="Bạn luôn có quyền quyết định"
      >
        Các lựa chọn chỉ áp dụng trong phiên demo. Không có dữ liệu nào được tải
        lên.
      </Intro>
      <Tabs
        defaultTab="privacy"
        tabs={{ privacy: "Quyền riêng tư", safety: "An toàn & báo cáo" }}
      />
      {tab === "privacy" ? <Privacy /> : <Safety />}
      <details className="app-about">
        <summary>Về Me2We</summary>
        <p>Hiểu mình hơn. Tìm người cùng tần số.</p>
        <p>
          Đây là bản trải nghiệm với nội dung mẫu, chưa kết nối thật. Nhân vật
          hư cấu, phản hồi soạn sẵn. Nội dung chỉ ở trong phiên, không được lưu
          sau khi tải lại.
        </p>
      </details>
      <DemoTools />
    </>
  );
}
function Privacy() {
  const { state, dispatch } = useDemo();
  const [off, setOff] = useState<Permission>();
  const [preview, setPreview] = useState(false);
  const [remove, setRemove] = useState<string>();
  const [identity, setIdentity] = useState("");
  return (
    <section className={cx.reading}>
      <h2>Bạn quyết định điều gì được dùng</h2>
      {(Object.keys(permissionCopy) as Permission[]).map((p) => (
        <label key={p} className={cx.permission}>
          <span>
            <strong>{permissionCopy[p].title}</strong>
            <small>{permissionCopy[p].description}</small>
            {p === "MATCH" && state.age === "teen" && (
              <small>Chưa mở cho nhân vật 16–17 tuổi.</small>
            )}
          </span>
          <input
            type="checkbox"
            role="switch"
            checked={state.consent[p]}
            disabled={p === "MATCH" && state.age === "teen"}
            onChange={(e) =>
              e.target.checked
                ? dispatch({ type: "PERMISSION", permission: p, on: true })
                : setOff(p)
            }
          />
        </label>
      ))}
      <p className={cx.note}>
        Tắt quyền không tự xóa mọi mục đã lưu. Tất cả nội dung mất khi tải lại
        hoặc đặt lại bản trải nghiệm.
      </p>
      <h3 className={cx.sectionTitle}>Dữ liệu của nhân vật demo</h3>
      <div className={cx.actions}>
        <Button variant="secondary" onClick={() => setPreview(true)}>
          Xem bản xuất dữ liệu giả
        </Button>
        {[
          ["mood", "Xóa tâm trạng"],
          ["ai", "Xóa hội thoại AI"],
          ["private", "Xóa hồ sơ riêng"],
        ].map(([v, l]) => (
          <Button variant="text" key={v} onClick={() => setRemove(v)}>
            {l}
          </Button>
        ))}
      </div>
      <h3 className={cx.sectionTitle}>Tên hiển thị demo</h3>
      <p>
        Chỉ chia sẻ khi đồng ý từng trường trong phòng chat. Đổi giá trị sẽ thu
        hồi quyền xem bản trước.
      </p>
      <form
        className={cx.simpleForm}
        onSubmit={(e) => {
          e.preventDefault();
          dispatch({ type: "IDENTITY", field: "displayName", text: identity });
          setIdentity("");
        }}
      >
        <label htmlFor="identity">
          Giá trị hiện tại: {state.identities.displayName}
        </label>
        <input
          id="identity"
          maxLength={40}
          value={identity}
          onChange={(e) => setIdentity(e.target.value)}
          placeholder="Dùng một tên hư cấu"
        />
        <Button type="submit" variant="secondary" disabled={!identity.trim()}>
          Sửa tên demo
        </Button>
      </form>
      {off && (
        <Dialog
          destructive
          title={`Tắt ${permissionCopy[off].title.toLocaleLowerCase("vi")}?`}
          onClose={() => setOff(undefined)}
        >
          <p>{permissionCopy[off].impact}</p>
          <p>Bật lại không khôi phục kết quả, phòng hoặc quyền đã thu hồi.</p>
          <div className={cx.actions}>
            <Button
              data-cancel
              variant="secondary"
              onClick={() => setOff(undefined)}
            >
              Hủy
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                dispatch({ type: "PERMISSION", permission: off, on: false });
                setOff(undefined);
              }}
            >
              Tắt quyền này
            </Button>
          </div>
        </Dialog>
      )}
      {preview && (
        <Dialog
          title="Bản xem dữ liệu hư cấu"
          onClose={() => setPreview(false)}
        >
          <p>
            Chỉ hiển thị số đếm và danh mục của nhân vật An. Không xuất nội dung
            bạn gõ, tin nhắn hay thông tin của đối phương; không tải xuống hoặc
            gửi đi.
          </p>
          <pre className={cx.exportPreview}>
            {JSON.stringify(safeExport(state), null, 2)}
          </pre>
          <Button onClick={() => setPreview(false)}>Đóng bản xem</Button>
        </Dialog>
      )}
      {remove && (
        <Dialog
          destructive
          title="Xóa loại dữ liệu này?"
          onClose={() => setRemove(undefined)}
        >
          <p>
            Nội dung bị xóa trong phiên demo. Xóa hồ sơ riêng sẽ ngừng các bản
            chia sẻ có liên quan và đóng phòng cũ.
          </p>
          <div className={cx.actions}>
            <Button
              data-cancel
              variant="secondary"
              onClick={() => setRemove(undefined)}
            >
              Hủy
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                dispatch({ type: "DELETE_TYPE", outcome: remove });
                setRemove(undefined);
              }}
            >
              Xóa dữ liệu đã chọn
            </Button>
          </div>
        </Dialog>
      )}
    </section>
  );
}
function Safety() {
  const { state, dispatch } = useDemo();
  const [candidate, setCandidate] = useState("C01"),
    [reason, setReason] = useState(""),
    [evidence, setEvidence] = useState<string[]>([]),
    [error, setError] = useState(""),
    [key, setKey] = useState(() => crypto.randomUUID()),
    [submitted, setSubmitted] = useState(false),
    [unblock, setUnblock] = useState<string>();
  return (
    <section className={cx.reading}>
      <ShieldCheck size={32} />
      <h2>Bạn có thể dừng kết nối bất cứ lúc nào</h2>
      <p>
        Chặn áp dụng ngay, không cần gửi báo cáo. Phiếu demo chỉ được lưu trong
        phiên, chưa gửi đến bộ phận xử lý hay nhân viên thật.
      </p>
      <h3>Nhân vật đã chặn</h3>
      {!state.blocked.length ? (
        <p>Chưa có nhân vật bị chặn.</p>
      ) : (
        state.blocked.map((id) => (
          <div className={cx.historyRow} key={id}>
            <strong>{state.candidates.find((c) => c.id === id)?.alias}</strong>
            <Button variant="secondary" onClick={() => setUnblock(id)}>
              Bỏ chặn
            </Button>
          </div>
        ))
      )}
      <h3 className={cx.sectionTitle}>Tạo báo cáo demo</h3>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!reason) {
            setError("Bạn chọn một lý do trước khi tạo phiếu nhé.");
            return;
          }
          dispatch({
            type: "REPORT",
            candidateId: candidate,
            reason,
            evidence,
            key,
          });
          setSubmitted(true);
          setError("");
        }}
      >
        <label htmlFor="report-person">Nhân vật hư cấu</label>
        <select
          id="report-person"
          value={candidate}
          onChange={(e) => {
            setCandidate(e.target.value);
            setSubmitted(false);
            setKey(crypto.randomUUID());
          }}
        >
          {state.candidates.map((c) => (
            <option key={c.id} value={c.id}>
              {c.alias}
            </option>
          ))}
        </select>
        <fieldset>
          <legend>Lý do báo cáo</legend>
          {[
            ["uncomfortable", "Nội dung khiến mình không thoải mái"],
            ["pressure", "Bị ép chia sẻ"],
            ["spam", "Tin lặp / làm phiền"],
            ["other", "Lý do khác"],
          ].map(([id, l]) => (
            <label key={id} className={cx.radioRow}>
              <input
                name="report-reason"
                type="radio"
                checked={reason === id}
                onChange={() => {
                  setReason(id);
                  setError("");
                }}
              />
              {l}
            </label>
          ))}
        </fieldset>
        <fieldset>
          <legend>Bằng chứng soạn sẵn · chọn tối đa 2</legend>
          <p>
            Đây là tình huống mẫu riêng, không lấy lại lịch sử chat đã đóng.
          </p>
          {[
            ["sample-1", "Tin mẫu: Yêu cầu chia sẻ liên hệ nhiều lần"],
            ["sample-2", "Tin mẫu: Lặp lại lời nhắn sau khi đã từ chối"],
          ].map(([id, l]) => (
            <label key={id} className={cx.radioRow}>
              <input
                type="checkbox"
                checked={evidence.includes(id)}
                onChange={(e) =>
                  setEvidence(
                    e.target.checked
                      ? [...evidence, id]
                      : evidence.filter((x) => x !== id),
                  )
                }
              />
              {l}
            </label>
          ))}
        </fieldset>
        {error && (
          <p role="alert" className={cx.error}>
            {error}
          </p>
        )}
        <div className={cx.actions}>
          <Button type="submit" disabled={submitted}>
            Tạo phiếu demo
          </Button>
          <Button
            variant="danger"
            onClick={() => dispatch({ type: "BLOCK", candidateId: candidate })}
          >
            Chặn ngay
          </Button>
          <Button
            variant="text"
            onClick={() => {
              setReason("");
              setEvidence([]);
              setError("");
              setSubmitted(false);
              setKey(crypto.randomUUID());
            }}
          >
            Hủy form
          </Button>
        </div>
      </form>
      {state.reports.map((r) => (
        <div className={cx.receipt} role="status" key={r.id}>
          <h3>Phiếu {r.id}</h3>
          <p>
            Chỉ lưu trong phiên demo. Chưa gửi đến bộ phận xử lý. Không có nhân
            viên thật nhận báo cáo.
          </p>
        </div>
      ))}
      <div className={cx.actions}>
        <Go secondary to="/home">
          Về hôm nay
        </Go>
      </div>
      {unblock && (
        <Dialog
          destructive
          title="Bỏ chặn nhân vật này?"
          onClose={() => setUnblock(undefined)}
        >
          <p>
            Phòng cũ, thông tin đã cho xem và thời gian chờ 30 ngày không được
            khôi phục.
          </p>
          <div className={cx.actions}>
            <Button
              data-cancel
              variant="secondary"
              onClick={() => setUnblock(undefined)}
            >
              Hủy
            </Button>
            <Button
              onClick={() => {
                dispatch({ type: "UNBLOCK", candidateId: unblock });
                setUnblock(undefined);
              }}
            >
              Bỏ chặn nhân vật
            </Button>
          </div>
        </Dialog>
      )}
    </section>
  );
}
export function DemoTools() {
  const { state, dispatch } = useDemo();
  const navigate = useNavigate();
  const [reset, setReset] = useState(false);

  return (
    <section className={cx.demoTools}>
      {import.meta.env.DEV &&
        new URLSearchParams(location.search).has("tools") && (
          <details>
            <summary>
              <SlidersHorizontal size={18} /> Công cụ demo · Dành cho kiểm thử
              nội bộ
            </summary>
            <p>
              Đồng hồ demo:{" "}
              {new Date(state.clock).toLocaleString("vi-VN", {
                timeZone: "Asia/Bangkok",
              })}{" "}
              · Asia/Bangkok. Nhóm tuổi đã chốt:{" "}
              {state.age === "teen" ? "16–17" : "Từ 18"}.
            </p>
            <p>
              Các điều khiển chỉ đổi tình huống mẫu, không cấp quyền hoặc đổi
              nhóm tuổi.
            </p>
            <div className={cx.actions}>
              <Button
                variant="secondary"
                onClick={() => dispatch({ type: "ERROR_ONCE" })}
              >
                {state.errorOnce ? "Tắt lỗi một lần" : "Thử lỗi một lần"}
              </Button>
              <Button
                variant="secondary"
                onClick={() =>
                  dispatch({
                    type: "OUTCOME",
                    outcome: state.outcome === "reply" ? "silent" : "reply",
                  })
                }
              >
                {state.outcome === "reply"
                  ? "Mô phỏng chưa trả lời"
                  : "Bật phản hồi mẫu"}
              </Button>
              <Button
                variant="secondary"
                onClick={() => dispatch({ type: "CLOCK", days: 8 })}
              >
                Tiến 8 ngày demo
              </Button>
              <Button
                variant="secondary"
                onClick={() => dispatch({ type: "CLOCK", days: 31 })}
              >
                Tiến 31 ngày demo
              </Button>
              <Button
                variant="secondary"
                onClick={() => dispatch({ type: "CLOCK", days: 1 / 1440 })}
              >
                Tiến 1 phút demo
              </Button>
            </div>
            <label htmlFor="preset">Dữ liệu mẫu cần thử</label>
            <select
              id="preset"
              defaultValue=""
              onChange={(e) => {
                if (e.target.value)
                  dispatch({ type: "PRESET", preset: e.target.value });
                e.target.value = "";
              }}
            >
              <option value="">Chọn dữ liệu mẫu</option>
              <option value="adult-ready-to-publish">
                Nháp mẫu, vẫn cần xem trước và chia sẻ
              </option>
              <option value="empty">Tâm trạng trống</option>
              <option value="insufficient">Tâm trạng chỉ 2 ngày</option>
              <option value="inbound-request">Lời mời đến từ Nắng Mai</option>
              <option value="stale-request">
                Lời mời khác bản hồ sơ hiện tại
              </option>
              <option value="expired-request">Lời mời hết hạn</option>
              <option value="reveal-gender">
                Trường giới tính hư cấu để QA
              </option>
            </select>
            <div className={cx.actions}>
              <Button
                variant="secondary"
                onClick={() =>
                  dispatch({ type: "PEER_CHANGE", candidateId: "C01" })
                }
              >
                Mô phỏng Lá Non sửa hồ sơ
              </Button>
              <Button
                variant="secondary"
                onClick={() =>
                  dispatch({
                    type: "PEER_CHANGE",
                    candidateId: "C01",
                    outcome: "revoke",
                  })
                }
              >
                Mô phỏng Lá Non ngừng chia sẻ
              </Button>
            </div>
          </details>
        )}
      <div className={cx.demoFooter}>
        <div>
          <Badge>Mọi dữ liệu chỉ ở trong phiên demo</Badge>
          <p>Tải lại trang hoặc đặt lại để bắt đầu câu chuyện mới.</p>
        </div>
        <div className={cx.actions}>
          <Button variant="text" onClick={() => setReset(true)}>
            Đặt lại bản trải nghiệm
          </Button>
        </div>
      </div>
      {reset && (
        <Dialog
          destructive
          title="Đặt lại bản trải nghiệm?"
          onClose={() => setReset(false)}
        >
          <p>
            Xóa thay đổi và hủy phản hồi đang chờ. Hồ sơ hư cấu ban đầu sẽ được
            nạp lại.
          </p>
          <div className={cx.actions}>
            <Button
              data-cancel
              variant="secondary"
              onClick={() => setReset(false)}
            >
              Hủy
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                dispatch({ type: "RESET" });
                setReset(false);
                navigate("/assistants", { replace: true });
              }}
            >
              Đặt lại toàn bộ
            </Button>
          </div>
        </Dialog>
      )}
    </section>
  );
}
