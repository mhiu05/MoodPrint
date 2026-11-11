import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type { SchoolReport } from "../../types";
import { schoolSeed } from "./school-data";
// Deliberately independent: this module never imports or reads the student store.
export const useSchoolStore = create<{
  reports: SchoolReport[];
  update: (report: SchoolReport) => void;
  reset: () => void;
}>()(
  persist(
    (set) => ({
      reports: structuredClone(schoolSeed),
      update: (report) =>
        set((s) => ({
          reports: s.reports.map((r) => (r.id === report.id ? report : r)),
        })),
      reset: () => set({ reports: structuredClone(schoolSeed) }),
    }),
    {
      name: "safevoice-school-demo",
      version: 1,
      storage: createJSONStorage(() => ({
        getItem: (key) => {
          try {
            return localStorage.getItem(key);
          } catch {
            return null;
          }
        },
        setItem: (key, value) => {
          try {
            localStorage.setItem(key, value);
          } catch {
            /* Local-only state still works. */
          }
        },
        removeItem: (key) => {
          try {
            localStorage.removeItem(key);
          } catch {
            /* Local-only state still works. */
          }
        },
      })),
    },
  ),
);
