import { errorMessage } from "../api/client";
import { Button, cx } from "./UI";

/** Shared by the public, guest and protected trees so none of them imports RealApp for it. */
export function ErrorNotice({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  if (!error) return null;
  return (
    <div className={cx.error} role="alert">
      <p>{errorMessage(error)}</p>
      {retry ? (
        <Button variant="secondary" onClick={retry}>
          Thử lại
        </Button>
      ) : null}
    </div>
  );
}
