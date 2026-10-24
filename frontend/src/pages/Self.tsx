import { useState, type FormEvent } from "react";
import { Link, Navigate } from "react-router-dom";
import { Smile, Meh, Frown, SmilePlus } from "lucide-react";
import { useDemo } from "../state/Provider";
import {
  Button,
  Badge,
  cx,
  Dialog,
  Go,
  Intro,
  Motion,
  Tabs,
  useTab,
} from "../components/UI";
import { effectiveAI } from "../domain/policies";
import { moodLabels } from "../mocks/fixtures";
import { demoDate, moodSummary } from "../domain/mood";
export function SelfPage() {
  const tab = useTab(["mood", "week", "chat", "profile"], "mood", ["topic"]);
  if (tab === "chat") return <Navigate replace to="/assistants/may" />;
  if (tab === "profile") return <Navigate replace to="/profile" />;
  return (
    <>
      <Intro eyebrow="MỘT CHÚT CHO MÌNH" title="Lắng nghe nhịp của mình" />
      <Tabs
        defaultTab="mood"
        tabs={{ mood: "Ghi cảm xúc", week: "Nhìn lại tuần" }}
      />
      {tab === "mood" ? <MoodPage /> : <Week />}
    </>
  );
}
const MoodIcons = [Frown, Meh, Meh, Smile, SmilePlus];
export function MoodPage() {
  const { state, dispatch } = useDemo();
  const [value, setValue] = useState(0),
    [note, setNote] = useState(""),
    [edit, setEdit] = useState<string | undefined>(),
    [remove, setRemove] = useState<string>();
  const today = demoDate(state.clock);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (value < 1) return;
    dispatch({
      type: "MOOD_SAVE",
      id: edit,
      date: edit ? state.moods.find((m) => m.id === edit)?.date : today,
      value,
      text: note,
    });
    setEdit(undefined);
    setValue(0);
    setNote("");
  };
  return (
    <section className={cx.reading}>
      <h2>Hôm nay bạn thấy thế nào?</h2>
      <p className={cx.lede}>Dừng một chút, lắng nghe mình.</p>
      <form onSubmit={submit}>
        <fieldset>
          <legend>
            {edit ? "Sửa ghi nhận đã chọn" : "Chọn một mức tâm trạng"}
          </legend>
          <div className={cx.moods}>
            {moodLabels.map((l, i) => {
              const Icon = MoodIcons[i];
              return (
                <Motion motionKey={value === i + 1 ? 1 : 0} kind="mood" key={l}>
                  <label
                    className={cx.moodOption}
                    data-selected={value === i + 1}
                  >
                    <input
                      type="radio"
                      name="mood"
                      checked={value === i + 1}
                      onChange={() => setValue(i + 1)}
                    />
                    <Icon size={29} strokeWidth={1.5} />
                    <strong className={cx.srOnly}>{i + 1}</strong>
                    <span>{l}</span>
                  </label>
                </Motion>
              );
            })}
          </div>
        </fieldset>
        <label htmlFor="mood-note">
          Một điều muốn ghi lại <small>Không bắt buộc</small>
        </label>
        <textarea
          id="mood-note"
          value={note}
          maxLength={120}
          rows={3}
          onChange={(e) => setNote(e.target.value)}
        />
        <div className={cx.actions}>
          <Button type="submit" disabled={value === 0}>
            {edit ? "Lưu thay đổi" : "Lưu tâm trạng"}
          </Button>
          {edit && (
            <Button
              variant="secondary"
              onClick={() => {
                setEdit(undefined);
                setValue(0);
                setNote("");
              }}
            >
              Hủy sửa
            </Button>
          )}
          <Go secondary to="/self?tab=week">
            Nhìn lại tuần
          </Go>
        </div>
      </form>
      <h3 className={cx.sectionTitle}>
        Những lần đã ghi <Badge>Mẫu & tự ghi</Badge>
      </h3>
      {!state.moods.length && (
        <p>Chưa có ghi nhận trong phiên này. Bạn có thể bắt đầu ở trên.</p>
      )}
      {[...state.moods]
        .sort((a, b) => b.date.localeCompare(a.date))
        .map((m) => (
          <div className={cx.historyRow} key={m.id}>
            <div>
              <strong>
                {m.date.slice(8)}/10 · {m.value}/5 — {moodLabels[m.value - 1]}
              </strong>
              <p>
                {m.note || "Không có ghi chú"} <small>· Tự ghi</small>
              </p>
            </div>
            <div className={cx.actions}>
              <Button
                variant="text"
                onClick={() => {
                  setEdit(m.id);
                  setValue(m.value);
                  setNote(m.note);
                  document
                    .querySelector<HTMLInputElement>("input[name=mood]")
                    ?.focus();
                }}
              >
                Sửa <span className={cx.srOnly}>{m.date}</span>
              </Button>
              <Button variant="text" onClick={() => setRemove(m.id)}>
                Xóa <span className={cx.srOnly}>{m.date}</span>
              </Button>
            </div>
          </div>
        ))}
      {remove && (
        <Dialog
          destructive
          title="Xóa ghi nhận này?"
          onClose={() => setRemove(undefined)}
        >
          <p>
            Biểu đồ sẽ tính lại từ những ngày còn được ghi. Hồ sơ kết nối không
            thay đổi.
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
                dispatch({ type: "MOOD_DELETE", id: remove });
                setRemove(undefined);
              }}
            >
              Xóa ghi nhận
            </Button>
          </div>
        </Dialog>
      )}
    </section>
  );
}
export function Week() {
  const { state } = useDemo();
  const s = moodSummary(state.moods, state.clock);
  const [selected, setSelected] = useState("");
  return (
    <section className={cx.reading}>
      <div className={cx.sectionHeading}>
        <div>
          <h2>Nhìn lại những ngày bạn đã ghi</h2>
          <p>7 ngày · Từ những lần tự ghi tâm trạng</p>
        </div>
        <Go secondary to="/self?tab=mood">
          Ghi thêm
        </Go>
      </div>
      <div className={cx.weekSummary}>
        <span>
          <strong>
            {s.mean === null
              ? "—"
              : s.mean.toLocaleString("vi-VN", {
                  minimumFractionDigits: 1,
                  maximumFractionDigits: 1,
                })}
          </strong>{" "}
          / 5
        </span>
        <p>
          Trung bình số học từ {s.count} ngày có ghi.
          <br />
          Đây không phải đánh giá sức khỏe.
        </p>
      </div>
      <svg
        viewBox="0 0 640 230"
        role="img"
        aria-label="Biểu đồ tâm trạng bảy ngày. Bảng dữ liệu đầy đủ ở bên dưới."
        className={cx.chart}
      >
        {[1, 2, 3, 4, 5].map((v) => (
          <g key={v}>
            <line
              x1="40"
              x2="620"
              y1={190 - (v - 1) * 40}
              y2={190 - (v - 1) * 40}
              stroke="#d8ded5"
            />
            <text x="12" y={195 - (v - 1) * 40}>
              {v}
            </text>
          </g>
        ))}
        {s.buckets.map((b, i) => (
          <g key={b.date}>
            {b.entry && (
              <>
                <line
                  x1={65 + i * 88}
                  x2={65 + i * 88}
                  y1="190"
                  y2={190 - (b.entry.value - 1) * 40}
                  stroke="#c1ccbb"
                  strokeWidth="2"
                />
                <circle
                  cx={65 + i * 88}
                  cy={190 - (b.entry.value - 1) * 40}
                  r="7"
                  fill="#285c4b"
                />
              </>
            )}
            <text x={65 + i * 88} y="220" textAnchor="middle">
              {b.date.slice(8)}/10
            </text>
          </g>
        ))}
      </svg>
      {s.count === 0 ? (
        <p className={cx.note}>Chưa có ghi nhận trong khoảng này.</p>
      ) : s.count < 3 ? (
        <p className={cx.note}>
          Cần ghi nhận ở ít nhất 3 ngày để xem xu hướng.
        </p>
      ) : effectiveAI(state) ? (
        <p className={cx.note}>
          Bạn đã dành thời gian cho mình trong {s.count}/7 ngày. Tâm trạng tự
          ghi từ {s.min} đến {s.max}/5.
        </p>
      ) : (
        <p className={cx.footnote}>
          AI đang tắt. Bảng và biểu đồ tự khai vẫn dùng được.
        </p>
      )}
      <details>
        <summary>Xem từng ngày</summary>
        <table className={cx.table}>
          <caption className={cx.srOnly}>
            Tâm trạng bảy ngày, ngày thiếu ghi là chưa ghi
          </caption>
          <thead>
            <tr>
              <th scope="col">Ngày</th>
              <th scope="col">Mức tự chọn</th>
              <th scope="col">Chi tiết</th>
            </tr>
          </thead>
          <tbody>
            {s.buckets.map((b) => (
              <tr key={b.date}>
                <th scope="row">{b.date.slice(8)}/10</th>
                <td>
                  {b.entry
                    ? `${b.entry.value} · ${moodLabels[b.entry.value - 1]}`
                    : "Chưa ghi"}
                </td>
                <td>
                  <Button
                    variant="text"
                    onClick={() =>
                      setSelected(
                        b.entry?.note || "Không có ghi chú cho ngày này.",
                      )
                    }
                  >
                    Xem <span className={cx.srOnly}>{b.date.slice(8)}/10</span>
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
      {selected && (
        <p className={cx.note} role="status">
          {selected}
        </p>
      )}
      <Link className={cx.textLink} to="/profile">
        Cùng xem hồ sơ của mình →
      </Link>
    </section>
  );
}
