import {
  createContext,
  useContext,
  useEffect,
  useReducer,
  useRef,
  type Dispatch,
  type ReactNode,
} from "react";
import type { Action, State } from "../domain/types";
import { demoState } from "../mocks/demo";
import { Scheduler } from "../mocks/scheduler";
import { reducer } from "./reducer";
const Context = createContext<{
  state: State;
  dispatch: Dispatch<Action>;
} | null>(null);
export function Provider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(
    (s: State, a: Action) =>
      a.type === "RESET" ? demoState(s.epoch + 1) : reducer(s, a),
    undefined,
    () => demoState(),
  );
  const scheduler = useRef(new Scheduler());
  useEffect(() => {
    scheduler.current.sync(state.jobs, dispatch);
  }, [state.jobs, state.epoch]);
  useEffect(() => () => scheduler.current.clear(), []);
  return (
    <Context.Provider value={{ state, dispatch }}>{children}</Context.Provider>
  );
}
export function useDemo() {
  const c = useContext(Context);
  if (!c) throw new Error("Demo provider missing");
  return c;
}
