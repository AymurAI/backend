import {
  type Dispatch,
  type ReactNode,
  createContext,
  useReducer,
} from "react";

import reducer, { type Action } from "@/reducers/file";
import type { DocFile } from "@/types/file";

/**
 * Context used to provide files that have to be processed
 */
export const FileContext = createContext<DocFile[]>([]);
FileContext.displayName = "FileContext";

/**
 * Context used to provide the dispatch function
 */
export const FileDispatchContext = createContext<Dispatch<Action>>(() => {});
FileDispatchContext.displayName = "FileDispatchContext";

interface Props {
  children: ReactNode;
}
export default function FileProvider({ children }: Props) {
  const [state, dispatch] = useReducer(reducer, []);

  return (
    <FileContext.Provider value={state}>
      <FileDispatchContext.Provider value={dispatch}>
        {children}
      </FileDispatchContext.Provider>
    </FileContext.Provider>
  );
}
