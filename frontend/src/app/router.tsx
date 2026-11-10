import { Root, Guard, Entry, NotFound, RouteError } from "./route-layouts";
import { lazy } from "react";
import { createBrowserRouter } from "react-router-dom";
import { StudentShell } from "../components/layout/StudentShell";
import { WelcomePage } from "../features/onboarding";
import { AuthPage, ResetPasswordPage } from "../features/auth";
import { HomePage } from "../features/home";
import { SettingsPage } from "../features/profile";
import { SchoolPage } from "../features/school-admin";
import { CaseList, CaseWizard, CaseDetail } from "../features/incidents";
import { PlanPage } from "../features/action-plans";
import { KnowledgeHub, ArticlePage } from "../features/knowledge";
import {
  SupportHome,
  FindHelpPage,
  SupportPreparePage,
  SupportRequestsPage,
  UrgentPage,
} from "../features/support";
const AIHub = lazy(() =>
  import("../features/ai").then((m) => ({ default: m.AIHub })),
);
const ChatPage = lazy(() =>
  import("../features/ai").then((m) => ({ default: m.ChatPage })),
);
const AnalysisPage = lazy(() =>
  import("../features/ai").then((m) => ({ default: m.AnalysisPage })),
);
const RoleplayPage = lazy(() =>
  import("../features/ai").then((m) => ({ default: m.RoleplayPage })),
);
export const router = createBrowserRouter([
  {
    element: <Root />,
    errorElement: <RouteError />,
    children: [
      { path: "/", element: <Entry /> },
      { path: "/welcome/:step", element: <WelcomePage /> },
      { path: "/auth", element: <AuthPage /> },
      { path: "/auth/reset", element: <ResetPasswordPage /> },
      { path: "/support/urgent", element: <UrgentPage /> },
      { path: "/demo/school", element: <SchoolPage /> },
      { path: "/demo/school/reports", element: <SchoolPage /> },
      { path: "/demo/school/reports/:id", element: <SchoolPage /> },
      {
        element: <Guard />,
        children: [
          {
            element: <StudentShell />,
            children: [
              { path: "/home", element: <HomePage /> },
              { path: "/settings", element: <SettingsPage /> },
              { path: "/ai", element: <AIHub /> },
              { path: "/ai/chat", element: <ChatPage /> },
              { path: "/ai/chat/:sessionId", element: <ChatPage /> },
              { path: "/ai/analysis/:analysisId", element: <AnalysisPage /> },
              { path: "/ai/roleplay", element: <RoleplayPage /> },
              { path: "/ai/roleplay/:role", element: <RoleplayPage /> },
              {
                path: "/ai/roleplay/:role/feedback",
                element: <RoleplayPage />,
              },
              { path: "/cases", element: <CaseList /> },
              { path: "/cases/new", element: <CaseWizard /> },
              { path: "/cases/:caseId/edit", element: <CaseWizard /> },
              { path: "/cases/:caseId/plan", element: <PlanPage /> },
              ...["", "/timeline", "/evidence", "/summary"].map((section) => ({
                path: `/cases/:caseId${section}`,
                element: <CaseDetail />,
              })),
              { path: "/support", element: <SupportHome /> },
              { path: "/support/find-help", element: <FindHelpPage /> },
              { path: "/support/prepare", element: <SupportPreparePage /> },
              { path: "/support/requests", element: <SupportRequestsPage /> },
              { path: "/support/knowledge", element: <KnowledgeHub /> },
              { path: "/knowledge/:slug", element: <ArticlePage /> },
              { path: "*", element: <NotFound /> },
            ],
          },
        ],
      },
    ],
  },
]);
