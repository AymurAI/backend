import { create } from "zustand";
import { useShallow } from "zustand/react/shallow";
import { devtools, persist } from "zustand/middleware";
import type { AnonymizerLabels } from "../types/aymurai";
import { FeatureFlowEnum } from "../types/features";

type TutorialsSeen = Record<FeatureFlowEnum, boolean>;

interface LocalStorageStore {
  serverHost: string | null;
  setServerHost: (serverUrl: string) => void;
  clearServerHost: () => void;
  tutorialsSeen: TutorialsSeen;
  hasSeenTutorial: (feature: FeatureFlowEnum) => boolean;
  setTutorialSeen: (feature: FeatureFlowEnum) => void;
  excludedTags: Record<AnonymizerLabels, boolean> | null;
  setExcludedTags: (tags: Record<AnonymizerLabels, boolean>) => void;
  excludedWords: string[];
  setExcludedWords: (words: string[]) => void;
  groupOrder: Record<string, string[]> | null;
  setGroupOrder: (order: Record<string, string[]>) => void;
  categoryAssignments: Record<string, string> | null;
  setCategoryAssignments: (assignments: Record<string, string>) => void;
}

const useLocalStore = create<LocalStorageStore>()(
  devtools(
    persist(
      (set, get) => ({
        serverHost: null,
        setServerHost: (serverHost: string) => set({ serverHost }),
        clearServerHost: () => set({ serverHost: null }),
        tutorialsSeen: {
          [FeatureFlowEnum.Anonymizer]: false,
          [FeatureFlowEnum.Dataset]: false,
        },
        hasSeenTutorial: (feature: FeatureFlowEnum) =>
          get().tutorialsSeen[feature],
        setTutorialSeen: (feature: FeatureFlowEnum) =>
          set((state) => ({
            tutorialsSeen: { ...state.tutorialsSeen, [feature]: true },
          })),
        excludedTags: null,
        setExcludedTags: (tags) => set({ excludedTags: tags }),
        excludedWords: [],
        setExcludedWords: (words) => set({ excludedWords: words }),
        groupOrder: null,
        setGroupOrder: (groupOrder) => set({ groupOrder }),
        categoryAssignments: null,
        setCategoryAssignments: (categoryAssignments) => set({ categoryAssignments }),
      }),
      {
        name: "local-storage",
      },
    ),
  ),
);

// TODO: in the future, we should export all of these hooks under a single named exports
// usage will be like the following: `localStore.useServerHost`
export const useServerHost = () => useLocalStore((state) => state.serverHost);
export const useServerHostActions = () => {
  const setServerHost = useLocalStore((state) => state.setServerHost);
  const clearServerHost = useLocalStore((state) => state.clearServerHost);

  return {
    setServerHost,
    clearServerHost,
  };
};

export const useTutorialSeen = (feature: FeatureFlowEnum) =>
  useLocalStore((state) => state.tutorialsSeen[feature]);
export const useSetTutorialSeen = () =>
  useLocalStore((state) => state.setTutorialSeen);

export const useExcludedTagsConfig = () =>
  useLocalStore(useShallow((s) => ({ tags: s.excludedTags, words: s.excludedWords })));
export const useExcludedTagsConfigActions = () =>
  useLocalStore(useShallow((s) => ({
    setTags: s.setExcludedTags,
    setWords: s.setExcludedWords,
  })));

export const useGroupOrder = () =>
  useLocalStore(useShallow((s) => ({
    groupOrder: s.groupOrder,
    categoryAssignments: s.categoryAssignments,
  })));
export const useGroupOrderActions = () =>
  useLocalStore(useShallow((s) => ({
    setGroupOrder: s.setGroupOrder,
    setCategoryAssignments: s.setCategoryAssignments,
  })));
