import { useState } from "react";

import { useFileDispatch } from "@/hooks";
import {
  removePredictionValueByCanonicalId,
  removePredictionsByCanonicalId,
  updatePredictionsByCanonicalId,
} from "@/reducers/file/actions";
import { sva } from "@/styled/css";
import { HStack } from "@/styled/jsx";
import { stack } from "@/styled/patterns";
import type { AllLabels, AllLabelsWithSufix } from "@/types/aymurai";
import LabelConfigTab from "./config-tab";
import LabelEntityTab from "./entity-tab";
import LabelManagerTab from "./tab";

const styles = sva({
  slots: ["container", "body", "close"],
  base: {
    container: {
      ...stack.raw({ gap: "11" }),
      px: "8",
      py: "6",
      width: "[400px]",
      overflow: "scroll",

      bg: "bg.primary",
    },
    body: {},
    close: {
      cursor: "pointer",
    },
  },
});

interface LabelManagerProps {
  onClose: () => void;
}
export default function LabelManager({ onClose }: LabelManagerProps) {
  const [selectedTab, setSelectedTab] = useState<"entity" | "config">("entity");
  const dispatch = useFileDispatch();

  const classes = styles();

  function handleDerivedGroupRemove(canonicalId: string) {
    dispatch(removePredictionsByCanonicalId(canonicalId));
  }

  function handleDerivedValueRemove(canonicalId: string, value: string) {
    dispatch(removePredictionValueByCanonicalId(canonicalId, value));
  }

  function handleDerivedLabelChange(
    canonicalId: string,
    labelId: string | undefined,
  ) {
    if (!labelId) return;
    dispatch(
      updatePredictionsByCanonicalId(
        canonicalId,
        labelId as AllLabels | AllLabelsWithSufix,
      ),
    );
  }

  return (
    <div className={classes.container}>
      <HStack justify="space-between" alignItems="flex-start">
        <HStack alignItems="center">
          <LabelManagerTab
            isSelected={selectedTab === "entity"}
            onClick={() => setSelectedTab("entity")}
          >
            Entidades
          </LabelManagerTab>
          <LabelManagerTab
            isSelected={selectedTab === "config"}
            onClick={() => setSelectedTab("config")}
          >
            Configuración
          </LabelManagerTab>
        </HStack>
        <button onClick={onClose} type="button" className={classes.close}>
          X
        </button>
      </HStack>
      <div className={classes.body}>
        {selectedTab === "entity" ? (
          <LabelEntityTab
            onDerivedGroupRemove={handleDerivedGroupRemove}
            onDerivedValueRemove={handleDerivedValueRemove}
            onDerivedLabelChange={handleDerivedLabelChange}
          />
        ) : (
          <LabelConfigTab />
        )}
      </div>
    </div>
  );
}
