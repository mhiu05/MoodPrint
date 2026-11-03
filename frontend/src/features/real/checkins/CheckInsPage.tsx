import { Navigate, useSearchParams } from "react-router-dom";
import { botById } from "../../../companions/registry";

/** Compatibility export for older route chunks; settings now live in each agent's info. */
export function CheckInsPage() {
  const [params] = useSearchParams();
  const id = params.get("bot");
  return <Navigate replace to={id && botById(id)
    ? `/assistants/${id}?panel=info&section=check-ins`
    : "/assistants?manageCheckIns=1"} />;
}
