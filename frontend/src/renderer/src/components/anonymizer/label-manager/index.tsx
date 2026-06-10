import { useState } from "react";

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useFileDispatch } from "@/hooks";
import {
  removePredictionValueByCanonicalId,
  removePredictionsByCanonicalId,
  updatePredictionsByCanonicalId,
} from "@/reducers/file/actions";
import { css, sva } from "@/styled/css";
import { HStack } from "@/styled/jsx";
import { stack } from "@/styled/patterns";
import type { AllLabels, AllLabelsWithSufix } from "@/types/aymurai";
import LabelConfigTab from "./config-tab";
import LabelEntityTab from "./entity-tab";
import LabelManagerTab from "./tab";

type ExpandedState = Record<string, boolean>;

const styles = sva({
  slots: ["container", "header", "body", "close"],
  base: {
    container: {
      ...stack.raw({ gap: "0" }),
      width: "[400px]",
      maxWidth: "[400px]",
      h: "full",
      minH: "0",
      flexShrink: "0",
      overflow: "hidden",
      overflowX: "hidden",

      bg: "bg.primary",
    },
    header: {
      px: "5",
      py: "6",
      pb: "4",
      flexShrink: "0",
      bg: "bg.primary",
      borderBottom: "[1px solid #BCBAB8]",
      zIndex: "1",
    },
    body: {
      px: "5",
      pt: "6",
      pb: "6",
      flex: "1",
      minH: "0",
      overflowY: "auto",
      overflowX: "hidden",
    },
    close: {
      cursor: "pointer",
    },
  },
});

const tooltipContent = css({
  bg: "action.hover",
  color: "white",
  px: "1.5",
  py: "0.5",
  rounded: "sm",
  fontSize: "[12px]",
  boxShadow: "[none]",
});

interface LabelManagerProps {
  onClose: () => void;
}
export default function LabelManager({ onClose }: LabelManagerProps) {
  const [selectedTab, setSelectedTab] = useState<"entity" | "config">("entity");
  const [expandedEntitySections, setExpandedEntitySections] =
    useState<ExpandedState>({});
  const [expandedEntityGroups, setExpandedEntityGroups] =
    useState<ExpandedState>({});
  const [expandedConfigSections, setExpandedConfigSections] =
    useState<ExpandedState>({});
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

  function handleEntitySectionOpenChange(section: string, open: boolean) {
    setExpandedEntitySections((prev) => ({ ...prev, [section]: open }));
  }

  function handleEntityGroupOpenChange(canonicalId: string, open: boolean) {
    setExpandedEntityGroups((prev) => ({ ...prev, [canonicalId]: open }));
  }

  function handleConfigSectionOpenChange(section: string, open: boolean) {
    setExpandedConfigSections((prev) => ({ ...prev, [section]: open }));
  }

  return (
    <div className={classes.container}>
      <TooltipProvider>
        <HStack
          justify="space-between"
          alignItems="flex-start"
          className={classes.header}
        >
          <HStack alignItems="center">
            <Tooltip>
              <TooltipTrigger asChild>
                <LabelManagerTab
                  isSelected={selectedTab === "entity"}
                  onClick={() => setSelectedTab("entity")}
                >
                  Entidades
                </LabelManagerTab>
              </TooltipTrigger>
              <TooltipContent showArrow={false} className={tooltipContent}>
                Revisar, editar y organizar los grupos de entidades reconocidos
              </TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <LabelManagerTab
                  isSelected={selectedTab === "config"}
                  onClick={() => setSelectedTab("config")}
                >
                  Configuración
                </LabelManagerTab>
              </TooltipTrigger>
              <TooltipContent showArrow={false} className={tooltipContent}>
                Elegir qué categorías anonimizar y definir términos excluidos
              </TooltipContent>
            </Tooltip>
          </HStack>
          <Tooltip>
            <TooltipTrigger asChild>
              <button onClick={onClose} type="button" className={classes.close}>
                X
              </button>
            </TooltipTrigger>
            <TooltipContent showArrow={false} className={tooltipContent}>
              Cerrar gestor de etiquetas
            </TooltipContent>
          </Tooltip>
        </HStack>
      </TooltipProvider>
      <div className={classes.body}>
        {selectedTab === "entity" ? (
          <LabelEntityTab
            expandedGroups={expandedEntityGroups}
            expandedSections={expandedEntitySections}
            onDerivedGroupRemove={handleDerivedGroupRemove}
            onDerivedValueRemove={handleDerivedValueRemove}
            onDerivedLabelChange={handleDerivedLabelChange}
            onGroupOpenChange={handleEntityGroupOpenChange}
            onSectionOpenChange={handleEntitySectionOpenChange}
          />
        ) : (
          <LabelConfigTab
            expandedSections={expandedConfigSections}
            onSectionOpenChange={handleConfigSectionOpenChange}
          />
        )}
      </div>
    </div>
  );
}
