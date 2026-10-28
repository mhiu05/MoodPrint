import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Button } from "../../components/UI";
import { useMotionPolicy } from "../../components/motion/useMotionPolicy";
import type { SessionView } from "../../api/contracts";
import type { components } from "../../api/generated/schema";
import { ErrorNotice, useResource, useSession } from "../real/RealApp";
import type { TourActivity } from "./tourActivity";
import { getTourSteps } from "./tourSteps";
import { useTourState } from "./useTourState";
import { waitForTourTarget } from "./waitForTourTarget";
import "./onboarding.css";

const BLOCKED = "Hãy hoàn tất hoặc đóng thao tác hiện tại rồi mở hướng dẫn.";
const hasActivity = (activity: TourActivity) =>
  activity.aiBusy || activity.voiceBusy || activity.hasDraft;

/** Shipped inline guide. No spotlight dependency, DOM content inspection or application writes. */
export default function TourController({
  session,
  activity,
  onClose,
}: {
  session: SessionView;
  activity: TourActivity;
  onClose?: () => void;
}) {
  const { api } = useSession();
  const navigate = useNavigate(),
    location = useLocation();
  const motion = useMotionPolicy();
  const availability =
    useResource<components["schemas"]["PublicExperience"]>(
      "/public/experience",
    );
  const { state, start, skip, finish, reset, setStep } = useTourState(session);
  const steps = useMemo(
    () => getTourSteps(session),
    [session.accountKind, session.ageBand, session.eligible],
  );
  const [running, setRunning] = useState(false),
    [waiting, setWaiting] = useState(false);
  const [index, setIndex] = useState(0),
    [notice, setNotice] = useState("");
  const pending = useRef<AbortController | null>(null);
  const target = useRef<HTMLElement | null>(null);
  const generation = useRef(0),
    focusFrame = useRef(0);
  const expectedRoute = useRef<string | null>(null);
  const currentActivity = useRef(activity);
  currentActivity.current = activity;
  const runningRef = useRef(running);
  runningRef.current = running;
  const title = useRef<HTMLHeadingElement>(null);
  const launcher = useRef(document.activeElement as HTMLElement | null);
  const release = useCallback(() => {
    ++generation.current;
    pending.current?.abort();
    pending.current = null;
    cancelAnimationFrame(focusFrame.current);
    target.current?.classList.remove("onboarding-target");
    target.current = null;
    expectedRoute.current = null;
  }, []);
  const restoreFocus = useCallback(() => {
    if (document.querySelector("dialog[open]")) return;
    const original = launcher.current;
    if (original?.isConnected && original.getBoundingClientRect().width > 0)
      original.focus();
    else document.querySelector<HTMLElement>("main h1")?.focus();
  }, []);
  const stop = useCallback(
    (message = "Bạn có thể xem lại hướng dẫn bất cứ lúc nào.") => {
      release();
      setRunning(false);
      setWaiting(false);
      skip();
      setNotice(message);
    },
    [release, skip],
  );
  const complete = useCallback(() => {
    release();
    setRunning(false);
    setWaiting(false);
    finish();
    setNotice("Bạn đã xem xong hướng dẫn.");
    restoreFocus();
  }, [release, finish, restoreFocus]);
  async function goToStep(next: number) {
    if (
      hasActivity(currentActivity.current) ||
      document.querySelector("dialog[open]")
    ) {
      stop(BLOCKED);
      return;
    }
    if (availability.data?.productTourAvailable !== true) {
      stop();
      return;
    }
    if (next >= steps.length) {
      complete();
      return;
    }
    release();
    const ticket = generation.current,
      authEpoch = api.epoch,
      controller = new AbortController();
    pending.current = controller;
    const step = steps[next];
    setRunning(true);
    setWaiting(true);
    setIndex(next);
    start();
    expectedRoute.current = step.route;
    navigate(step.route);
    const found = await waitForTourTarget(step.target, controller.signal);
    if (
      controller.signal.aborted ||
      generation.current !== ticket ||
      api.epoch !== authEpoch
    )
      return;
    if (
      hasActivity(currentActivity.current) ||
      document.querySelector("dialog[open]")
    ) {
      stop(BLOCKED);
      return;
    }
    if (!found) {
      if (next === 0)
        stop("Chưa thể mở hướng dẫn ở màn hình này. Thử lại sau.");
      else {
        setNotice("Một bước chưa sẵn sàng; chuyển sang bước tiếp theo.");
        void goToStep(next + 1);
      }
      return;
    }
    target.current = found;
    found.classList.add("onboarding-target");
    found.scrollIntoView({ block: "nearest", behavior: "auto" });
    setWaiting(false);
    setStep(step.id);
    focusFrame.current = requestAnimationFrame(() => {
      if (
        !controller.signal.aborted &&
        generation.current === ticket &&
        api.epoch === authEpoch &&
        !document.querySelector("dialog[open]")
      )
        title.current?.focus();
    });
  }
  useEffect(() => () => release(), [release]);
  useEffect(() => {
    if (running && (hasActivity(activity) || !motion.visible)) stop(BLOCKED);
  }, [
    activity.aiBusy,
    activity.voiceBusy,
    activity.hasDraft,
    running,
    motion.visible,
    stop,
  ]);
  useEffect(() => {
    if (running && availability.data?.productTourAvailable === false)
      stop("Hướng dẫn đang tạm dừng. Bạn vẫn có thể đọc các bước bên dưới.");
  }, [running, availability.data?.productTourAvailable, stop]);
  useEffect(() => {
    if (
      runningRef.current &&
      expectedRoute.current &&
      location.pathname !== expectedRoute.current
    )
      stop("Hướng dẫn đã dừng khi bạn chuyển màn hình.");
  }, [location.pathname, stop]);
  useEffect(() => {
    const observer = new MutationObserver(() => {
      if (runningRef.current && document.querySelector("dialog[open]"))
        stop(BLOCKED);
    });
    observer.observe(document.body, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ["open"],
    });
    const escape = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || document.querySelector("dialog[open]"))
        return;
      event.preventDefault();
      stop();
      restoreFocus();
    };
    document.addEventListener("keydown", escape);
    return () => {
      observer.disconnect();
      document.removeEventListener("keydown", escape);
    };
  }, [stop, restoreFocus]);
  useEffect(() => {
    const refresh = () => availability.refresh();
    window.addEventListener("focus", refresh);
    return () => window.removeEventListener("focus", refresh);
  }, [availability.refresh]);
  return (
    <aside className="onboarding-guide" aria-labelledby="onboarding-title">
      <div className="onboarding-header">
        <h2 id="onboarding-title">Hướng dẫn nhanh</h2>
        <Button
          variant="text"
          onClick={() => {
            release();
            onClose?.();
            restoreFocus();
          }}
        >
          Đóng hướng dẫn
        </Button>
      </div>
      {notice ? <p role="status">{notice}</p> : null}
      {availability.loading && !availability.data ? (
        <p role="status">Đang mở hướng dẫn…</p>
      ) : null}
      <ErrorNotice error={availability.error} retry={availability.refresh} />
      {running ? (
        <>
          <p role="status">
            Bước {index + 1}/{steps.length}
          </p>
          <h3 tabIndex={-1} ref={title}>
            {steps[index]?.title}
          </h3>
          <p>{steps[index]?.description}</p>
          {waiting ? <p role="status">Đang tìm vị trí hướng dẫn…</p> : null}
          <div className="onboarding-actions">
            <Button
              variant="secondary"
              disabled={waiting || index === 0}
              onClick={() => void goToStep(index - 1)}
            >
              Quay lại
            </Button>
            {index === steps.length - 1 ? (
              <Button disabled={waiting} onClick={complete}>
                Hoàn tất
              </Button>
            ) : (
              <Button
                disabled={waiting}
                onClick={() => void goToStep(index + 1)}
              >
                Tiếp
              </Button>
            )}
            <Button
              variant="text"
              onClick={() => {
                stop();
                restoreFocus();
              }}
            >
              Bỏ qua
            </Button>
          </div>
        </>
      ) : (
        <>
          <p>
            Bốn bước ngắn, không thay đổi dữ liệu hay quyền của bạn. Bạn có thể
            đóng và xem lại bất cứ lúc nào.
          </p>
          <ol aria-label="Các bước hướng dẫn">
            {steps.map((step) => (
              <li key={step.id}>
                <strong>{step.title}</strong>
                <p>{step.description}</p>
                <Link to={step.route}>{step.title}</Link>
              </li>
            ))}
          </ol>
          {availability.data?.productTourAvailable ? (
            <Button
              onClick={() => {
                reset();
                setNotice("");
                void goToStep(0);
              }}
            >
              {state.status === "idle"
                ? "Bắt đầu hướng dẫn"
                : "Xem lại hướng dẫn"}
            </Button>
          ) : null}
        </>
      )}
    </aside>
  );
}
