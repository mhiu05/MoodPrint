import { useState, type FormEvent } from "react";
import { Brand, Button } from "../../components/UI";
import type { components } from "../../api/generated/schema";
import type { SessionView } from "../../api/contracts";
import { ErrorNotice, useSession } from "./RealApp";

function currentYear(serverTime: string) {
  return Number(
    new Intl.DateTimeFormat("en", {
      timeZone: "Asia/Bangkok",
      year: "numeric",
    }).format(new Date(serverTime)),
  );
}

function AgeForm({ upgrade = false }: { upgrade?: boolean }) {
  const { api, session, receive } = useSession();
  const [year, setYear] = useState(session.birthYear?.toString() || "");
  const [minimum, setMinimum] = useState(Boolean(session.eligible && session.birthYear));
  const [adult, setAdult] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const serverYear = currentYear(session.serverTime);
  const boundaryAdultYear = Number(year) === serverYear - 18;
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !minimum || (upgrade && boundaryAdultYear && !adult)) return;
    setBusy(true);
    setError(undefined);
    try {
      const result = await api.request<SessionView>("/users/me/eligibility", {
        method: "PUT",
        body: {
          birthYear: Number(year),
          confirmedMinimumAge: minimum,
          confirmedAdultAge: boundaryAdultYear && adult,
          expectedVersion: session.eligibilityVersion || 0,
          policyVersion: "self-declared-age-v1",
        } satisfies components["schemas"]["EligibilityInput"],
      });
      receive(result);
    } catch (reason) {
      setError(reason);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="real-age-form" onSubmit={submit} aria-busy={busy}>
      <ErrorNotice error={error} />
      <label htmlFor="birth-year">Năm sinh</label>
      <input
        id="birth-year"
        type="number"
        inputMode="numeric"
        autoComplete="bday-year"
        min={1900}
        max={serverYear}
        required
        readOnly={session.birthYear != null}
        value={year}
        onChange={(event) => {
          setYear(event.target.value);
          setAdult(false);
        }}
      />
      <label className="real-age-confirmation">
        <input
          type="checkbox"
          required
          checked={minimum}
          onChange={(event) => setMinimum(event.target.checked)}
        />
        <span>Tôi xác nhận mình đã đủ 16 tuổi.</span>
      </label>
      {boundaryAdultYear && (
        <label className="real-age-confirmation">
          <input
            type="checkbox"
            checked={adult}
            onChange={(event) => setAdult(event.target.checked)}
          />
          <span>
            Tôi xác nhận mình đã đủ 18 tuổi để sử dụng Tìm bạn và nhắn tin người
            thật.
          </span>
        </label>
      )}
      {boundaryAdultYear && !upgrade && (
        <p>Bạn vẫn có thể dùng các tính năng cá nhân nếu chưa đủ 18 tuổi.</p>
      )}
      <Button
        type="submit"
        disabled={
          busy || !minimum || !year || (upgrade && boundaryAdultYear && !adult)
        }
      >
        {busy
          ? "Đang xác nhận…"
          : upgrade
            ? "Xác nhận đủ 18 tuổi"
            : "Xác nhận năm sinh"}
      </Button>
    </form>
  );
}

export function EligibilityGate() {
  const { session, logout } = useSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const canDeclare =
    session.ageBand === "unknown" ||
    (session.ageBand === "under16" &&
      session.birthYear != null &&
      currentYear(session.serverTime) - session.birthYear >= 16);
  return (
    <main className="real-auth">
      <Brand />
      <h1 tabIndex={-1}>
        {canDeclare
          ? "Trước khi bắt đầu"
          : "Ứng dụng dành cho người từ 16 tuổi"}
      </h1>
      {canDeclare ? (
        <>
          <p>
            Hãy nhập năm sinh và xác nhận bạn đã đủ 16 tuổi. Tìm bạn và nhắn tin
            người thật dành cho người đã đủ 18 tuổi.
          </p>
          <p>Năm sinh không xuất hiện trong hồ sơ kết nối của bạn.</p>
          <AgeForm />
        </>
      ) : (
        <p>
          Bạn chưa đủ điều kiện sử dụng. Bạn có thể quay lại khi đã đủ 16 tuổi.
        </p>
      )}
      <ErrorNotice error={error} />
      <Button
        variant="text"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          setError(undefined);
          try {
            await logout();
          } catch (reason) {
            setError(reason);
          } finally {
            setBusy(false);
          }
        }}
      >
        Đăng xuất
      </Button>
    </main>
  );
}

export function AdultEligibility() {
  const { session } = useSession();
  if (session.ageBand !== "teen") return null;
  const canConfirm =
    session.birthYear != null &&
    currentYear(session.serverTime) - session.birthYear >= 18;
  return (
    <section className="real-section">
      <h2>Điều kiện kết nối</h2>
      <p>
        Tìm bạn và nhắn tin người thật dành cho người đã đủ 18 tuổi. Bạn vẫn có
        thể dùng các tính năng cá nhân.
      </p>
      {canConfirm && <AgeForm upgrade />}
    </section>
  );
}
