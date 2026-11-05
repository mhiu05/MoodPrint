import { useState, type FormEvent } from "react";
import { Brand, Button } from "../../components/UI";
import type { SessionView } from "../../api/contracts";
import { ErrorNotice, useSession } from "./RealApp";
import { AccountActions, AccountDeletionComplete } from "./AccountActions";
import { AgeFields } from "../auth/AgeFields";
import { ageDeclaration, bangkokYear } from "../auth/ageDeclaration";

function AgeForm() {
  const { api, session, receive } = useSession();
  const [year, setYear] = useState(session.birthYear?.toString() || "");
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const serverYear = bangkokYear(session.serverTime);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !confirmed) return;
    setBusy(true);
    setError(undefined);
    try {
      const result = await api.request<SessionView>("/users/me/eligibility", {
        method: "PUT",
        body: ageDeclaration(
          year,
          confirmed,
          serverYear,
          session.eligibilityVersion || 0,
        ),
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
      <AgeFields
        year={year}
        confirmed={confirmed}
        currentYear={serverYear}
        onYear={setYear}
        onConfirmed={setConfirmed}
        readOnly={session.birthYear != null}
      />
      <Button type="submit" disabled={busy || !confirmed || !year}>
        {busy ? "Đang xác nhận…" : "Xác nhận và tiếp tục"}
      </Button>
    </form>
  );
}

export function EligibilityGate() {
  const { session } = useSession();
  const [deleted, setDeleted] = useState(false);
  const canDeclare =
    session.birthYear == null ||
    bangkokYear(session.serverTime) - session.birthYear >= 18;
  if (deleted)
    return (
      <main className="real-auth">
        <AccountDeletionComplete />
      </main>
    );
  return (
    <main className="real-auth">
      <Brand />
      <h1 tabIndex={-1}>
        {canDeclare
          ? "Xác nhận độ tuổi"
          : "MoodPrint dành cho người từ đủ 18 tuổi."}
      </h1>
      <p>Bạn cần đủ 18 tuổi để sử dụng MoodPrint.</p>
      {canDeclare ? (
        <>
          <p>Hãy nhập năm sinh và xác nhận bạn đã qua sinh nhật lần thứ 18.</p>
          <p>Năm sinh không xuất hiện trong hồ sơ tìm bạn của bạn.</p>
          <AgeForm key={`${session.birthYear ?? "unknown"}:${session.eligibilityVersion ?? 0}`} />
        </>
      ) : (
        <p>
          Dữ liệu tài khoản của bạn được giữ nguyên. Bạn có thể quay lại khi đã
          đủ 18 tuổi.
        </p>
      )}
      <AccountActions
        restricted
        onGuide={() => {}}
        onDeleted={() => setDeleted(true)}
      />
    </main>
  );
}

/** Existing adult accounts do not need a second social-only age declaration. */
export function AdultEligibility() {
  return null;
}
