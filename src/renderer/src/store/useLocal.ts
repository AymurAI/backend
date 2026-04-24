import { create } from "zustand";
import { devtools, persist } from "zustand/middleware";

interface LocalStorageStore {
  serverHost: string | null;
  setServerHost: (serverUrl: string) => void;
  clearServerHost: () => void;
}

const useLocalStore = create<LocalStorageStore>()(
  devtools(
    persist(
      (set) => ({
        serverHost: null,
        setServerHost: (serverHost: string) => set({ serverHost }),
        clearServerHost: () => set({ serverHost: null }),
      }),
      {
        name: "local-storage",
      },
    ),
  ),
);

const useServerHost = () => useLocalStore((state) => state.serverHost);
const useServerHostActions = () => {
  const setServerHost = useLocalStore((state) => state.setServerHost);
  const clearServerHost = useLocalStore((state) => state.clearServerHost);

  return {
    setServerHost,
    clearServerHost,
  };
};

export const localStore = {
  useServerHost,
  useServerHostActions,
};
