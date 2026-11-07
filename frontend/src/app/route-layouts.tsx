import { Suspense, useEffect } from "react";
import { Navigate, Outlet, useLocation, useRouteError } from "react-router-dom";
import { useDemoStore } from "./store";
import { useVisualViewport } from "../hooks/useVisualViewport";
import { Toast } from "../components/layout/StudentShell";
import { EmptyState, LinkButton, Skeleton } from "../components/ui";
export function Root() {
  useVisualViewport();
  const reduced = useDemoStore((s) => s.preferences.reducedMotion);
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
  const user = useDemoStore((s) => s.user);
  const location = useLocation();
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
  const user = useDemoStore((s) => s.user);
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
        title="Trang demo cần được mở lại"
        description={
          error instanceof Error
            ? error.message
            : "Có lỗi khi tải trang. Dữ liệu demo vẫn được giữ trên trình duyệt."
        }
        action={<LinkButton to="/">Mở lại MoodPrint</LinkButton>}
      />
    </main>
  );
}
