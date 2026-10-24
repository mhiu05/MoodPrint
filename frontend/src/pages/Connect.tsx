import { useEffect, useState } from "react";
import { Link, useSearchParams, useNavigate } from "react-router-dom";
import { ArrowUpRight, Clock, Check, Leaf } from "lucide-react";
import { useDemo } from "../state/Provider";
import { recommendations } from "../domain/matching";
import { canChat, canMatch } from "../domain/policies";
import {
  Avatar,
  Badge,
  Button,
  cx,
  Dialog,
  Go,
  Intro,
  Motion,
  StatePanel,
  Tabs,
  useTab,
} from "../components/UI";
import { labels } from "../mocks/fixtures";
export const requestStatus: Record<string, string> = {
  pending: "Đang chờ",
  accepted: "Đã đồng ý",
  cancelled: "Đã hủy",
  declined: "Đã từ chối",
  expired: "Đã hết hạn",
  invalidated: "Không còn hợp lệ",
};
export function ConnectPage() {
  const { state, dispatch } = useDemo();
  const navigate = useNavigate();
  const tab = useTab(["discover", "requests"], "discover", ["reason"]);
  const [params] = useSearchParams();
  const [reason, setReason] = useState<string>();
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (tab !== "discover" || !canMatch(state)) return;
    setLoading(true);
    const fail = state.errorOnce;
    if (fail) dispatch({ type: "ERROR_ONCE" });
    const timer = setTimeout(() => {
      setFailed(fail);
      setLoading(false);
    }, 400);
    return () => clearTimeout(timer);
  }, [tab, state.profileVersion, state.consent.MATCH, state.age]);
  const list = recommendations(state);
  const selected = list.find((x) => x.candidate.id === reason);
  return (
    <>
      <Intro eyebrow="TÌM BẠN" title="Gặp người cùng tần số">
        Một điểm chung, nhiều câu chuyện mới.
      </Intro>
      <Tabs
        defaultTab="discover"
        tabs={{ discover: "Khám phá", requests: "Lời mời & kết nối" }}
      />
      {params.get("reason") && (
        <p role="status" className={cx.note}>
          Phòng không tồn tại, đã đóng hoặc bạn chưa có quyền truy cập. Không có
          nội dung chat nào được mở.
        </p>
      )}
      {state.age === "teen" ? (
        <TeenConcept />
      ) : !canMatch(state) ? (
        <StatePanel
          title="Giới thiệu mình bằng vài điều bạn thích"
          action={<Go to="/profile?tab=sharing">Soạn hồ sơ kết nối</Go>}
        >
          Bạn cần xem trước, cho phép chia sẻ hồ sơ và bật quyền tìm bạn. AI có
          thể giữ tắt.
        </StatePanel>
      ) : tab === "requests" ? (
        <Requests />
      ) : loading ? (
        <StatePanel title="Đang tìm những điểm chung…">
          Chỉ dùng những mục bạn đã chọn chia sẻ.
        </StatePanel>
      ) : failed ? (
        <StatePanel
          title="Chưa hiện được gợi ý mẫu"
          action={
            <Button onClick={() => setFailed(false)}>Thử lại gợi ý</Button>
          }
        >
          Hồ sơ và lựa chọn của bạn vẫn được giữ.
        </StatePanel>
      ) : (
        <>
          <div className={cx.sectionHeading}>
            <p>Một điểm chung để bắt đầu.</p>
            <Link className={cx.textLink} to="/profile?tab=sharing">
              Sửa hồ sơ <ArrowUpRight size={16} />
            </Link>
          </div>
          <Motion
            kind="cards"
            motionKey={`${state.profileVersion}-${list.map((x) => x.candidate.id).join()}`}
            className={cx.matchGrid}
          >
            {list.map(({ candidate: c, score, reasons }) => (
              <article key={c.id} className={cx.matchCard}>
                <div className={cx.matchCardTop}>
                  <Avatar name={c.alias} color={c.color} />
                  <div>
                    <Badge>
                      {
                        (
                          {
                            C01: "Một cuốn sách, một tách trà",
                            C02: "Học thêm, đi xa hơn",
                            C03: "Nhặt nắng qua ống kính",
                            C04: "Chậm rãi và lắng nghe",
                          } as Record<string, string>
                        )[c.id]
                      }
                    </Badge>
                    <h2>{c.alias}</h2>
                  </div>
                </div>
                <p className={cx.cardLead}>
                  {
                    (
                      {
                        C01: "Mê truyện ngắn và những công thức nấu ăn mới.",
                        C02: "Đang tìm bạn luyện tiếng Anh, thích đi bộ lúc chiều.",
                        C03: "Luôn có một playlist cho những ngày đầy nắng.",
                        C04: "Thích đọc sách, đi dạo và nghe bạn kể chuyện.",
                      } as Record<string, string>
                    )[c.id]
                  }
                </p>
                <div className={cx.chips}>
                  {state
                    .published!.interests.filter((x) =>
                      c.profile.interests.includes(x),
                    )
                    .map((x) => (
                      <Badge key={x}>{labels[x]}</Badge>
                    ))}
                </div>
                <Button variant="text" onClick={() => setReason(c.id)}>
                  Vì sao được gợi ý?
                </Button>
                <div className={cx.actions}>
                  <Button
                    onClick={() => {
                      dispatch({ type: "REQUEST_SEND", candidateId: c.id });
                      navigate("/connect?tab=requests");
                    }}
                  >
                    Làm quen <ArrowUpRight size={17} />
                  </Button>
                  <Button
                    variant="text"
                    onClick={() =>
                      dispatch({ type: "SKIP", candidateId: c.id })
                    }
                  >
                    Bỏ qua
                  </Button>
                  <Button
                    variant="text"
                    onClick={() =>
                      dispatch({ type: "BLOCK", candidateId: c.id })
                    }
                  >
                    Chặn
                  </Button>
                </div>
              </article>
            ))}
          </Motion>
          {!list.length && (
            <StatePanel
              title="Chưa có gợi ý mới"
              action={
                <div className={cx.actions}>
                  <Go to="/connect?tab=requests">Xem lời mời</Go>
                  <Go secondary to="/profile?tab=sharing">
                    Xem lại lựa chọn
                  </Go>
                </div>
              }
            >
              Các nhân vật có thể đang chờ lời mời, đã được bỏ qua hoặc chưa đáp
              ứng lựa chọn hiện tại.
            </StatePanel>
          )}
          <div className={cx.actions}>
            <Go secondary to="/connect?tab=requests">
              Xem lời mời & kết nối
            </Go>
          </div>
        </>
      )}
      {selected && (
        <Dialog
          title={`Điểm chung với ${selected.candidate.alias}`}
          onClose={() => setReason(undefined)}
        >
          <ul>
            {selected.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
          <p>
            Chỉ dùng sở thích và lựa chọn bạn đã chia sẻ. Tâm trạng và chuyện
            riêng không dùng để tìm bạn.
          </p>
          <Button onClick={() => setReason(undefined)}>Mình đã hiểu</Button>
        </Dialog>
      )}
    </>
  );
}
export function TeenConcept() {
  return (
    <>
      <StatePanel
        title="Có những điểm chung để tìm hiểu"
        action={
          <div className={cx.actions}>
            <Go to="/self?tab=mood">Quay lại hiểu bản thân</Go>
            <Go secondary to="/profile?tab=sharing">
              Thử soạn bản nháp
            </Go>
          </div>
        }
      >
        Nhân vật demo 16–17 tuổi chưa được dùng kết nối/chat người lạ trong bản
        trải nghiệm này. Bạn có thể tìm hiểu ví dụ tĩnh dưới đây.
      </StatePanel>
      <section className={cx.concept}>
        <Leaf size={35} />
        <Badge>Ví dụ tĩnh · Không tạo kết nối</Badge>
        <h3>Hai người cùng thích đọc sách</h3>
        <p>
          Có thể bắt đầu bằng việc chia sẻ một cuốn sách yêu thích. Khi sản phẩm
          có cách kết nối phù hợp độ tuổi, người dùng sẽ được xem trước điều
          muốn chia sẻ.
        </p>
      </section>
      <Concepts />
    </>
  );
}
export function Concepts() {
  const [preview, setPreview] = useState<string>();
  const concepts = [
    [
      "Học cùng nhau",
      "Cùng tập trung học 25 phút",
      "25:00",
      "Một khoảng tập trung bên nhau. Đồng hồ chỉ minh họa.",
    ],
    [
      "Luyện tiếng Anh",
      "Luyện nói qua chủ đề thú vị",
      "Aa",
      "What book would you recommend to a friend?",
    ],
    [
      "Trò chơi nhỏ",
      "Chơi một trò nhỏ",
      "✳",
      "Một câu đố, hai cách nghĩ. Cùng tìm đáp án nhé!",
    ],
  ];
  return (
    <div className={cx.concepts}>
      <div className={cx.conceptGrid}>
        {concepts.map(([t, d, art]) => (
          <button className={cx.concept} key={t} onClick={() => setPreview(t)}>
            <span className={cx.conceptArt}>{art}</span>
            <h4>{t}</h4>
            <p>{d}</p>
            <small>Xem thử ↗</small>
          </button>
        ))}
      </div>
      {preview && (
        <Dialog title={preview} onClose={() => setPreview(undefined)}>
          <Badge>Đang thử nghiệm · Bản xem trước</Badge>
          <div className={cx.activityPreview}>
            {concepts.find((c) => c[0] === preview)?.[2]}
          </div>
          <p>{concepts.find((c) => c[0] === preview)?.[3]}</p>
          <p>
            Hoạt động này chưa có phiên chơi. Bạn có thể thử Câu hỏi làm quen
            ngay.
          </p>
          <Button onClick={() => setPreview(undefined)}>
            Về hoạt động chung
          </Button>
        </Dialog>
      )}
    </div>
  );
}
function Requests() {
  const { state, dispatch } = useDemo();
  return (
    <section>
      <h2>Kết nối của bạn</h2>
      <p>Chỉ trò chuyện khi cả hai cùng đồng ý.</p>
      {state.connections
        .filter((c) => canChat(state, c))
        .map((c) => (
          <Motion key={c.id} kind="success" motionKey={c.id}>
            <div className={cx.connectionRow}>
              <Avatar
                name={
                  state.candidates.find((x) => x.id === c.candidateId)!.alias
                }
              />
              <div>
                <Badge>
                  <Check size={13} /> Cả hai đã đồng ý
                </Badge>
                <h3>
                  {state.candidates.find((x) => x.id === c.candidateId)!.alias}
                </h3>
              </div>
              <Go to={`/chat/${c.id}`}>Mở trò chuyện</Go>
            </div>
          </Motion>
        ))}
      {!state.requests.length && (
        <StatePanel
          title="Chưa có lời mời trong phiên này"
          action={<Go to="/connect">Tìm người chung sở thích</Go>}
        >
          Bạn có thể bắt đầu từ một điểm chung.
        </StatePanel>
      )}
      {[...state.requests].reverse().map((r) => {
        const alias = state.candidates.find(
          (x) => x.id === r.candidateId,
        )!.alias;
        return (
          <article className={cx.requestRow} key={r.id}>
            <div className={cx.sectionHeading}>
              <div>
                <h3>{alias}</h3>
                <p>
                  {r.direction === "out"
                    ? "Bạn đã gửi lời mời"
                    : "Lời mời gửi đến bạn"}{" "}
                  · Nhân vật giả lập
                </p>
              </div>
              <Badge>
                <Clock size={13} />
                {requestStatus[r.status]}
              </Badge>
            </div>
            {r.status === "pending" ? (
              <>
                <p>Chờ một lời đồng ý để câu chuyện bắt đầu.</p>
                {r.direction === "out" ? (
                  <>
                    <Button
                      variant="secondary"
                      onClick={() =>
                        dispatch({
                          type: "REQUEST_DECIDE",
                          id: r.id,
                          outcome: "cancel",
                        })
                      }
                    >
                      Hủy lời mời
                    </Button>
                    <div className={cx.simulation}>
                      <small>Mô phỏng đối phương</small>
                      <div className={cx.actions}>
                        {[
                          ["accept", "Đồng ý"],
                          ["decline", "Từ chối"],
                          ["expire", "Hết hạn"],
                        ].map(([o, l]) => (
                          <Button
                            variant="secondary"
                            key={o}
                            onClick={() =>
                              dispatch({
                                type: "REQUEST_DECIDE",
                                id: r.id,
                                outcome: o,
                              })
                            }
                          >
                            {l}
                          </Button>
                        ))}
                      </div>
                    </div>
                  </>
                ) : (
                  <div className={cx.actions}>
                    <Button
                      onClick={() =>
                        dispatch({
                          type: "REQUEST_DECIDE",
                          id: r.id,
                          outcome: "accept",
                        })
                      }
                    >
                      Đồng ý lời mời
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={() =>
                        dispatch({
                          type: "REQUEST_DECIDE",
                          id: r.id,
                          outcome: "decline",
                        })
                      }
                    >
                      Từ chối lời mời
                    </Button>
                    <Button
                      variant="text"
                      onClick={() =>
                        dispatch({
                          type: "REQUEST_SEND",
                          candidateId: r.candidateId,
                        })
                      }
                    >
                      Gửi lời mời chéo
                    </Button>
                  </div>
                )}
              </>
            ) : (
              <p>
                {r.status === "accepted"
                  ? "Kết nối chỉ mở khi hồ sơ và quyền hiện tại vẫn hợp lệ."
                  : "Lời mời này không mở phòng chat. Cặp sẽ tạm ngừng gợi ý trong 30 ngày demo."}
              </p>
            )}
          </article>
        );
      })}
      {state.connections
        .filter((c) => !canChat(state, c))
        .map((c) => (
          <div className={cx.historyRow} key={c.id}>
            <p>
              {state.candidates.find((x) => x.id === c.candidateId)?.alias} ·{" "}
              {c.status === "blocked" ? "Đã chặn" : "Đã kết thúc"}. Không thể
              đọc lại nội dung phòng.
            </p>
            <Go secondary to={`/settings?tab=safety`}>
              An toàn & báo cáo
            </Go>
          </div>
        ))}
    </section>
  );
}
