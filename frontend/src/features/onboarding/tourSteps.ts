import type { SessionView } from "../../api/contracts";

export type TourStep = {
  id: "assistants" | "mood" | "memory" | "privacy" | "matching";
  route: string;
  target: string;
  title: string;
  description: string;
  isApplicable: (session: SessionView) => boolean;
};
