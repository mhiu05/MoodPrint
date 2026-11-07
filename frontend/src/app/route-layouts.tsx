import { Suspense, useEffect } from "react";
import {
  Navigate,
  Outlet,
  useLocation,
  useNavigate,
  useRouteError,
} from "react-router-dom";
import { useWorkspaceStore } from "./store";
import { useVisualViewport } from "../hooks/useVisualViewport";
import { Toast } from "../components/layout/StudentShell";
import {
  Button,
  EmptyState,
  LinkButton,
  Notice,
  Skeleton,
} from "../components/ui";
import { hydrateWorkspace, initializeWorkspace } from "../services/workspace";
export function Root() {
  useVisualViewport();
  const reduced = useWorkspaceStore((s) => s.preferences.reducedMotion);
  const navigate = useNavigate();
  const location = useLocation();
  useEffect(() => {
    void initializeWorkspace();
  }, []);
  useEffect(() => {
    const expired = () =>
      navigate("/auth", {
        state: { from: location.pathname + location.search },
        replace: true,
      });
    window.addEventListener("moodprint:unauthenticated", expired);
    return () =>
      window.removeEventListener("moodprint:unauthenticated", expired);
  }, [navigate, location.pathname, location.search]);
  useEffect(() => {
    document.documentElement.dataset.reducedMotion = String(reduced);
  }, [reduced]);
  return (
    <>
      <Suspense fallback={<Skeleton />}>
        <Outlet />
      </Suspense>
      <Toast />
    </>
  );
}
export function Guard() {
  const user = useWorkspaceStore((s) => s.user);
  const hydration = useWorkspaceStore((s) => s.hydration);
  const location = useLocation();
  if (hydration.status === "initializing" || hydration.status === "loading")
    return <Skeleton />;
  if (hydration.status === "error")
    return (
      <main className="page-content">
        <Notice tone="error">{hydration.error}</Notice>
        <Button
          onClick={() => {
            const state = useWorkspaceStore.getState();
            void (
              state.workspace.kind === "real" && state.workspace.userId
                ? hydrateWorkspace()
                : initializeWorkspace()
            ).catch(() => {});
          }}
        >
          Thử lại
        </Button>
        <LinkButton to="/auth" variant="secondary">
          Đăng nhập
        </LinkButton>
      </main>
    );
  return user ? (
    <Outlet />
  ) : (
    <Navigate
      to="/auth"
      state={{ from: location.pathname + location.search }}
      replace
    />
  );
}
export function Entry() {
  const user = useWorkspaceStore((s) => s.user);
  const hydration = useWorkspaceStore((s) => s.hydration);
  if (hydration.status === "initializing" || hydration.status === "loading")
    return <Skeleton />;
  return <Navigate to={user ? "/home" : "/welcome/1"} replace />;
}
export function NotFound() {
  return (
    <EmptyState
      title="Mình chưa tìm thấy trang này"
      description="Bạn có thể quay lại không gian của mình và chọn một lối đi khác."
      action={<LinkButton to="/home">Về Home</LinkButton>}
    />
  );
}
export function RouteError() {
  const error = useRouteError();
  return (
    <main className="page-content">
      <EmptyState
        title="Trang cần được mở lại"
        description={
          error instanceof Error
            ? error.message
            : "Có lỗi khi tải trang. Hãy mở lại để tiếp tục."
        }
        action={<LinkButton to="/">Mở lại MoodPrint</LinkButton>}
      />
    </main>
  );
}
