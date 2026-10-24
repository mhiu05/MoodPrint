import type { Action, Job } from "../domain/types";
export class Scheduler {
  private timers = new Map<string, ReturnType<typeof setTimeout>>();
  sync(jobs: Job[], dispatch: (a: Action) => void) {
    const ids = new Set(jobs.map((j) => j.id));
    for (const [id, timer] of this.timers)
      if (!ids.has(id)) {
        clearTimeout(timer);
        this.timers.delete(id);
      }
    for (const job of jobs)
      if (!this.timers.has(job.id))
        this.timers.set(
          job.id,
          setTimeout(() => {
            this.timers.delete(job.id);
            dispatch(job.event);
          }, job.delay),
        );
  }
  clear() {
    for (const timer of this.timers.values()) clearTimeout(timer);
    this.timers.clear();
  }
  get size() {
    return this.timers.size;
  }
}
