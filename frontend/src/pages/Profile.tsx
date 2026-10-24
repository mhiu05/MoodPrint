import { MiniMoodChart } from "../companions/Cards";
import { Link } from "react-router-dom";
import { useState } from "react";
import { LockKeyhole, Check, Eye, Leaf } from "lucide-react";
import { useDemo } from "../state/Provider";
import {
  Button,
  Badge,
  cx,
  Dialog,
  Go,
  Intro,
  Tabs,
  useTab,
} from "../components/UI";
import {
  goals,
  interests,
  labels,
  languages,
  sampleProfile,
  styles,
  values,
} from "../mocks/fixtures";
import type { Profile } from "../domain/types";
import { effectiveMemory, validProfile } from "../domain/policies";
export function ProfilePage() {
  const tab = useTab(["private", "sharing"], "private");
  return (
    <>
      <Intro eyebrow="Từng chút một, hiểu mình hơn" title="Một chút về tôi">
        Điều giữ riêng, điều sẻ chia — luôn do bạn chọn.
      </Intro>
      <Tabs
        defaultTab="private"
        tabs={{ private: "Chỉ mình xem", sharing: "Hồ sơ kết nối" }}
      />
      {tab === "private" ? (
        <>
          <div className="profile-summary">
            <span className="profile-monogram">A</span>
            <div>
              <h2>Chào An,</h2>
              <p>Cứ là bạn, theo cách của bạn.</p>
            </div>
            <Link to="/settings" aria-label="Cài đặt và quyền riêng tư">
              <LockKeyhole size={20} />
            </Link>
          </div>
          <div className="profile-mood">
            <MiniMoodChart />
          </div>
          <PrivateProfile />
        </>
      ) : (
        <Sharing />
      )}
    </>
  );
}
const statuses = {
  proposed: "Đề xuất đang chờ",
  confirmed: "Đã xác nhận",
  edited: "Bạn đã sửa",
  rejected: "Đã từ chối",
  deleted: "Đã xóa",
};
export function PrivateProfile() {
  const { state, dispatch } = useDemo();
  const [edit, setEdit] = useState<string>(),
    [text, setText] = useState(""),
    [add, setAdd] = useState(""),
    [remove, setRemove] = useState<string>();
  return (
    <section className={cx.reading}>
      <div className={cx.sectionHeading}>
        <div>
          <h2>Bạn là người hiểu mình rõ nhất</h2>
          <p>
            <LockKeyhole size={16} aria-hidden="true" /> Chỉ bạn xem được các
            mục này.
          </p>
        </div>
        <Go secondary to="/profile?tab=sharing">
          Soạn hồ sơ kết nối
        </Go>
      </div>

      {state.privateItems
        .filter((x) => !["rejected", "deleted"].includes(x.status))
        .map((item) => (
          <article className={cx.privateItem} key={item.id}>
            <div className={cx.actions}>
              <Badge>
                {item.origin === "ai" ? "AI gợi ý mẫu" : "Bạn tự khai"}
              </Badge>
              <small>{statuses[item.status]}</small>
            </div>
            <h3>{item.text}</h3>
            {item.origin === "ai" && (
              <p className={cx.footnote}>
                Một gợi ý để bạn cân nhắc, sửa hoặc bỏ qua.
              </p>
            )}
            <div className={cx.actions}>
              {item.status === "proposed" && (
                <>
                  <Button
                    variant="secondary"
                    onClick={() =>
                      dispatch({
                        type: "PRIVATE_CHANGE",
                        id: item.id,
                        outcome: "confirm",
                      })
                    }
                  >
                    <Check size={16} />
                    Đúng với mình
                  </Button>
                  <Button
                    variant="text"
                    onClick={() =>
                      dispatch({
                        type: "PRIVATE_CHANGE",
                        id: item.id,
                        outcome: "reject",
                      })
                    }
                  >
                    Không đúng
                  </Button>
                </>
              )}
              <Button
                variant="text"
                onClick={() => {
                  setEdit(item.id);
                  setText(item.text);
                }}
              >
                Sửa lại <span className={cx.srOnly}>{item.id}</span>
              </Button>
              <Button variant="text" onClick={() => setRemove(item.id)}>
                Xóa <span className={cx.srOnly}>{item.id}</span>
              </Button>
            </div>
            {item.origin === "ai" &&
              ["confirmed", "edited"].includes(item.status) && (
                <div className={cx.memoryRow}>
                  <p>
                    {item.memoryApproved
                      ? "Bạn đã cho phép dùng lại trong phiên này."
                      : "Chưa cho phép dùng lại khi trò chuyện."}{" "}
                    {!effectiveMemory(state) &&
                      "AI cần cả quyền trò chuyện và ghi nhớ để dùng mục này."}
                  </p>
                  <Button
                    variant="secondary"
                    disabled={!effectiveMemory(state) || item.memoryApproved}
                    onClick={() =>
                      dispatch({
                        type: "PRIVATE_CHANGE",
                        id: item.id,
                        outcome: "memory",
                      })
                    }
                  >
                    Cho phép dùng trong phiên
                  </Button>
                </div>
              )}
          </article>
        ))}
      {!state.privateItems.some((x) => x.status === "proposed") && (
        <p className={cx.note}>Không còn đề xuất cần xem.</p>
      )}
      <form
        className={cx.simpleForm}
        onSubmit={(e) => {
          e.preventDefault();
          if (!add.trim()) return;
          dispatch({ type: "PRIVATE_ADD", text: add });
          setAdd("");
        }}
      >
        <label htmlFor="private-add">Thêm một điều về mình</label>
        <input
          id="private-add"
          maxLength={120}
          value={add}
          onChange={(e) => setAdd(e.target.value)}
          placeholder="Ví dụ: Mình thích đi bộ"
        />
        <Button type="submit" variant="secondary" disabled={!add.trim()}>
          Thêm mục riêng
        </Button>
      </form>
      {edit && (
        <Dialog
          title="Sửa điều bạn muốn giữ lại"
          onClose={() => setEdit(undefined)}
        >
          <label htmlFor="private-edit">Nội dung mẫu</label>
          <textarea
            id="private-edit"
            maxLength={120}
            rows={4}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <p>
            Nếu mục này đã được liên kết vào hồ sơ kết nối, bản đang chia sẻ sẽ
            mất hiệu lực và các phòng dùng bản đó sẽ đóng. Bản sửa không tự được
            chia sẻ.
          </p>
          <div className={cx.actions}>
            <Button
              disabled={!text.trim()}
              onClick={() => {
                dispatch({
                  type: "PRIVATE_CHANGE",
                  id: edit,
                  text,
                  outcome: "edit",
                });
                setEdit(undefined);
              }}
            >
              Lưu thay đổi
            </Button>
            <Button variant="secondary" onClick={() => setEdit(undefined)}>
              Hủy
            </Button>
          </div>
        </Dialog>
      )}
      {remove && (
        <Dialog
          destructive
          title="Xóa mục riêng này?"
          onClose={() => setRemove(undefined)}
        >
          <p>
            Nếu hồ sơ kết nối đang dùng mục này làm nguồn, hồ sơ đó và các kết
            nối dùng bản cũ sẽ ngừng hoạt động.
          </p>
          <div className={cx.actions}>
            <Button
              variant="secondary"
              data-cancel
              onClick={() => setRemove(undefined)}
            >
              Hủy
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                dispatch({
                  type: "PRIVATE_CHANGE",
                  id: remove,
                  outcome: "delete",
                });
                setRemove(undefined);
              }}
            >
              Xóa mục riêng
            </Button>
          </div>
        </Dialog>
      )}
    </section>
  );
}
export function Preview({ profile }: { profile: Profile }) {
  return (
    <div className={cx.preview}>
      <span className={cx.previewAvatar}>
        <Leaf size={32} />
      </span>
      <h3>An</h3>
      <p>Người khác chỉ xem những điều dưới đây</p>
      <h4>Sở thích</h4>
      <div className={cx.chips}>
        {profile.interests.map((x) => (
          <Badge key={x}>{labels[x]}</Badge>
        ))}
      </div>
      <h4>Điều mình coi trọng</h4>
      <div className={cx.chips}>
        {profile.values.map((x) => (
          <Badge key={x}>{labels[x]}</Badge>
        ))}
      </div>
      <p>{labels[profile.style] || "Chưa chọn cách trò chuyện"}</p>
      <p>{labels[profile.goal] || "Chưa chọn mục tiêu"}</p>
      <p>
        {profile.languages.map((x) => labels[x]).join(" · ") ||
          "Chưa chọn ngôn ngữ"}
      </p>
    </div>
  );
}
export function Sharing() {
  const { state, dispatch } = useDemo();
  const [preview, setPreview] = useState<Profile>(),
    [withdraw, setWithdraw] = useState(false);
  const p = state.draft;
  const update = (next: Profile) => dispatch({ type: "DRAFT", profile: next });
  const toggle = (group: "interests" | "values" | "languages", id: string) => {
    const next = {
      ...p,
      [group]: p[group].includes(id)
        ? p[group].filter((x) => x !== id)
        : [...p[group], id],
    };
    if (
      group === "interests" &&
      id === "reading" &&
      !next.interests.includes(id)
    )
      next.sources = [];
    update(next);
  };
  const source = state.privateItems.find(
    (x) => x.id === "PI01" && ["confirmed", "edited"].includes(x.status),
  );
  return (
    <section>
      <div className={cx.sharingHeading}>
        <div>
          <h2>Chọn những điểm chung để bắt đầu</h2>
          <p>
            Chỉ những mục trong bản xem trước được dùng để gợi ý. Không cần bật
            AI.
          </p>
        </div>
        <Button variant="secondary" onClick={() => update(sampleProfile())}>
          Dùng lựa chọn mẫu
        </Button>
      </div>
      {state.age === "teen" && (
        <p className={cx.note}>
          Nhân vật 16–17 tuổi chỉ soạn và xem nháp trong demo này. Chưa thể chia
          sẻ, gửi lời mời hoặc chat người lạ.
        </p>
      )}
      {state.published?.valid && (
        <div className={cx.published}>
          <Badge>Đang chia sẻ</Badge>
          <p>
            Sửa nháp hoặc hủy xem trước vẫn giữ bản đang chia sẻ. Xuất bản thay
            thế sẽ đóng các phòng dùng bản cũ.
          </p>
          <Button variant="text" onClick={() => setWithdraw(true)}>
            Ngừng chia sẻ
          </Button>
        </div>
      )}
      <div className={cx.sharingGrid}>
        <div>
          {(
            [
              ["interests", interests, "Sở thích · chọn ít nhất 3"],
              ["values", values, "Điều bạn coi trọng · chọn ít nhất 2"],
              ["languages", languages, "Ngôn ngữ có thể trò chuyện"],
            ] as const
          ).map(([group, dict, title]) => (
            <fieldset key={group} className={cx.tagField}>
              <legend>
                {title} <small>({p[group].length} đã chọn)</small>
              </legend>
              <div className={cx.tags}>
                {Object.entries(dict).map(([id, label]) => (
                  <label key={id} data-selected={p[group].includes(id)}>
                    <input
                      type="checkbox"
                      checked={p[group].includes(id)}
                      onChange={() => toggle(group, id)}
                    />
                    {label}
                  </label>
                ))}
              </div>
            </fieldset>
          ))}
          {source && (
            <label className={cx.sourceOption}>
              <input
                type="checkbox"
                checked={!!p.sources.length}
                onChange={(e) =>
                  update({
                    ...p,
                    interests: e.target.checked
                      ? Array.from(new Set([...p.interests, "reading"]))
                      : p.interests,
                    sources: e.target.checked
                      ? [{ id: source.id, version: source.version }]
                      : [],
                  })
                }
              />
              <span>
                Liên kết với sở thích “Đọc sách” của mình
                <small>
                  Chỉ ánh xạ tag Đọc sách. Nội dung riêng không được đưa vào hồ
                  sơ.
                </small>
              </span>
            </label>
          )}
          <label htmlFor="style">Cách bạn thích trò chuyện</label>
          <select
            id="style"
            value={p.style}
            onChange={(e) => update({ ...p, style: e.target.value })}
          >
            <option value="">Chọn một cách</option>
            {Object.entries(styles).map(([id, l]) => (
              <option key={id} value={id}>
                {l}
              </option>
            ))}
          </select>
          <label htmlFor="goal">Bạn muốn tìm gì?</label>
          <select
            id="goal"
            value={p.goal}
            onChange={(e) => update({ ...p, goal: e.target.value })}
          >
            <option value="">Chọn mục tiêu</option>
            {Object.entries(goals).map(([id, l]) => (
              <option key={id} value={id}>
                {l}
              </option>
            ))}
          </select>
          <div className={cx.actions}>
            <Button onClick={() => setPreview(structuredClone(p))}>
              <Eye size={17} />
              Xem trước hồ sơ
            </Button>
          </div>
          <p className={cx.footnote}>
            Nháp chỉ ở trong phiên demo, chưa dùng để tìm bạn.
          </p>
        </div>
        <aside className={cx.sharingAside}>
          <LockKeyhole size={28} />
          <h3>Những điều thuộc về riêng bạn</h3>
          <p>
            Tâm trạng, hội thoại AI, ghi nhớ, tên hiển thị và giới tính không
            được dùng để gợi ý kết nối.
          </p>
          <p>Chia sẻ là một lựa chọn. Để sau cũng được.</p>
        </aside>
      </div>
      {preview && (
        <Dialog
          title="Bạn muốn chia sẻ thông tin này chứ?"
          onClose={() => setPreview(undefined)}
        >
          <Preview profile={preview} />
          {!validProfile(preview) && (
            <p role="alert" className={cx.error}>
              Cần ít nhất 3 sở thích, 2 giá trị, cách trò chuyện, mục tiêu và
              ngôn ngữ.
            </p>
          )}
          {state.age === "adult" && (
            <label className={cx.radioRow}>
              <input
                type="checkbox"
                checked={state.consent.MATCH}
                onChange={(e) =>
                  dispatch({
                    type: "PERMISSION",
                    permission: "MATCH",
                    on: e.target.checked,
                  })
                }
              />
              Cho phép dùng hồ sơ này để tìm bạn
            </label>
          )}
          <p className={cx.footnote}>
            Chỉ các mục trên được dùng để tìm điểm chung.{" "}
            {state.published?.valid
              ? "Thay bản sẽ đóng các phòng dùng bản cũ."
              : ""}
          </p>
          <div className={cx.actions}>
            <Button
              disabled={
                state.age !== "adult" ||
                !state.consent.MATCH ||
                !validProfile(preview)
              }
              onClick={() => {
                dispatch({ type: "PUBLISH", profile: preview });
                setPreview(undefined);
              }}
            >
              Cho phép chia sẻ
            </Button>
            <Button variant="secondary" onClick={() => setPreview(undefined)}>
              Mình chưa muốn chia sẻ
            </Button>
          </div>
          {state.age === "teen" && (
            <p>Chưa mở chia sẻ cho nhân vật 16–17 tuổi.</p>
          )}
        </Dialog>
      )}
      {state.published?.valid && (
        <div className={cx.actions}>
          <Go to="/connect">Xem những người có điểm chung</Go>
        </div>
      )}
      {withdraw && (
        <Dialog
          destructive
          title="Ngừng chia sẻ hồ sơ kết nối?"
          onClose={() => setWithdraw(false)}
        >
          <p>
            Lời mời sẽ bị hủy, phòng đang dùng hồ sơ này sẽ đóng, quyền xem tên
            và hoạt động chung sẽ dừng. Bật lại không mở lại phòng cũ.
          </p>
          <div className={cx.actions}>
            <Button
              data-cancel
              variant="secondary"
              onClick={() => setWithdraw(false)}
            >
              Hủy
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                dispatch({ type: "WITHDRAW" });
                setWithdraw(false);
              }}
            >
              Ngừng chia sẻ hồ sơ
            </Button>
          </div>
        </Dialog>
      )}
    </section>
  );
}
