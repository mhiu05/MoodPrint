import type { TourStep } from "./tourSteps";

export type TourCallbacks = { next: () => void; back: () => void; skip: () => void; finish: () => void };
export type TourAdapter = {
  show: (target: HTMLElement, step: TourStep, index: number, total: number) => void;
  refresh: () => void;
  destroy: () => void;
};
