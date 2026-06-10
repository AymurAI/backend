import { useContext } from "react";

import { FileContext, FileDispatchContext } from "@/context/File";

/**
 * Hook used to view the files in the state
 */
export function useFiles() {
  return useContext(FileContext);
}

/**
 * Hook used to dispatch actions that modify the state
 */
export function useFileDispatch() {
  return useContext(FileDispatchContext);
}
