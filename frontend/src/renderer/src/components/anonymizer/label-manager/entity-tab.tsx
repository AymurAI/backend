import AnonymizerLabelSelect from "@/components/anonymizer/anonymizer-label-select";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  ANONYMIZER_CATEGORY_NAMES,
  getAnonymizerCategoryForLabel,
  getLabelsPrioritizingCategory,
} from "@/constants/anonymizer-categories";
import { useFileDispatch, useFiles } from "@/hooks";
import { useEntityGroups } from "@/hooks/useEntityGroups";
import {
  mergeGroups,
  moveMentionToGroup,
  removePredictionValueByCanonicalId,
  removePredictionsByCanonicalId,
  updatePredictionsByCanonicalId,
} from "@/reducers/file/actions";
import { useHoverState } from "@/store/useHoverState";
import { css } from "@/styled/css";
import { HStack, Stack, styled } from "@/styled/jsx";
import type { AllLabels, AllLabelsWithSufix } from "@/types/aymurai";
import {
  DndContext,
  type DragEndEvent,
  type DragOverEvent,
  DragOverlay,
  type DragStartEvent,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useDraggable,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import {
  ArrowsLeftRight,
  DotsSixVertical,
  PlusCircle,
  Trash,
  Warning,
  XCircle,
} from "phosphor-react";
import { useEffect, useMemo, useState } from "react";

import type { EntityGroup } from "@/hooks/useEntityGroups";
import {
  useExcludedTagsConfig,
  useGroupOrder,
  useGroupOrderActions,
} from "@/store/useLocal";
import { normalizeEntityText } from "@/utils/anonymizer/entity-similarity";
import { filterActivePredictions } from "@/utils/anonymizer/predictions";
import MergeDialog from "./merge-dialog";
import RemoveDialog from "./remove-dialog";
import LabelManagerSection from "./section";
import SortableGroup from "./sortable-group";

function normalizeText(t: string) {
  return normalizeEntityText(t);
}

const GROUP_PREFIX = "group:";
const TEXT_PREFIX = "text:";

function groupDndId(id: string) {
  return `${GROUP_PREFIX}${id}`;
}
function textDndId(canonicalId: string, normText: string) {
  return `${TEXT_PREFIX}${canonicalId}:::${normText}`;
}
function parseGroupDndId(id: string): string | null {
  return id.startsWith(GROUP_PREFIX) ? id.slice(GROUP_PREFIX.length) : null;
}
function parseTextDndId(
  id: string,
): { canonicalId: string; text: string } | null {
  if (!id.startsWith(TEXT_PREFIX)) return null;
  const rest = id.slice(TEXT_PREFIX.length);
  const sep = rest.indexOf(":::");
  if (sep === -1) return null;
  return { canonicalId: rest.slice(0, sep), text: rest.slice(sep + 3) };
}

const iconButton = css({
  cursor: "pointer",
  color: "text.lighter",
  bg: "transparent",
  border: "[1px solid #BCBAB8]",
  rounded: "sm",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  p: "1.5",
  flexShrink: "0",
  "&:hover": {
    color: "white",
    bg: "action.hover",
    borderColor: "action.hover",
  },
});

const suffixBadge = css({
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  px: "1.5",
  py: "0.5",
  bg: "[#E6E8FF]",
  color: "[#3F479D]",
  rounded: "xs",
  fontVariantNumeric: "tabular-nums",
  userSelect: "none",
  flexShrink: "1",
  minW: "0",
  maxW: "full",
  overflowWrap: "anywhere",
  wordBreak: "break-word",
  whiteSpace: "normal",
  textAlign: "right",
  fontSize: "[11px]",
  fontWeight: "bold",
  letterSpacing: "wide",
});

const textItemSplitHighlight = {
  bg: "[#D9DCFF]",
  boxShadow: "[inset 0 0 0 1px #8A92D8]",
} as const;

const textItemConfirmingSplitHighlight = {
  bg: "[#C8CDF8]",
  boxShadow: "[inset 0 0 0 2px #6F78CE]",
} as const;

const textItemStyle = css({
  display: "flex",
  alignItems: "flex-start",
  gap: "1",
  px: "1.5",
  py: "0.5",
  bg: "bg.primary-alternative",
  rounded: "xs",
  minW: "0",
  w: "full",
  boxSizing: "border-box",
  "&:hover": textItemSplitHighlight,
});

const textItemDraggingStyle = css({ opacity: "0.35" });
const textItemPendingSplitStyle = css(textItemSplitHighlight);
const textItemConfirmingSplitStyle = css({
  ...textItemConfirmingSplitHighlight,
  "&:hover": textItemConfirmingSplitHighlight,
});

const textContextMenu = css({
  position: "fixed",
  zIndex: "60",
  minW: "[150px]",
  bg: "bg.primary",
  border: "[1px solid #BCBAB8]",
  rounded: "sm",
  boxShadow: "[0_8px_20px_rgba(17,0,65,0.14)]",
  p: "1",
});

const textContextMenuButton = css({
  display: "flex",
  alignItems: "center",
  gap: "1.5",
  w: "full",
  px: "2",
  py: "1.5",
  bg: "transparent",
  border: "none",
  rounded: "xs",
  cursor: "pointer",
  color: "text.default",
  textStyle: "label.md.default",
  textAlign: "left",
  "&:hover": {
    bg: "[#D9DCFF]",
    color: "[#1B0D58]",
  },
  "&:focus-visible": {
    outline: "[2px solid #3F479D]",
    outlineOffset: "[1px]",
  },
});

const groupCardStyle = css({
  bg: "bg.primary",
  border: "[1px solid #BCBAB8]",
  rounded: "sm",
  minW: "0",
  w: "full",
});

// Used for both drag-over drop target and hover — same inset outline + violet bg
const groupHoverStyle = css({
  bg: "bg.primary-alternative",
  boxShadow: "[inset 0 0 0 2px #3F479D]",
});

const duplicateBadge = css({
  display: "inline-flex",
  alignItems: "center",
  gap: "1",
  px: "1.5",
  py: "0.5",
  bg: "[#ECEEFF]",
  color: "[#3F479D]",
  border: "[1px solid #7B84D4]",
  rounded: "xs",
  fontSize: "[11px]",
  fontWeight: "semibold",
  cursor: "pointer",
  maxW: "full",
  minW: "0",
  overflow: "hidden",
  "& > span": {
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  "&:hover": { bg: "[#D8DBFF]" },
});

const groupHeader = css({
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "1",
  minW: "0",
});

const groupHeaderLeft = css({
  display: "flex",
  alignItems: "center",
  minW: "0",
  flex: "1",
  overflow: "hidden",
});

interface DraggableTextChipProps {
  canonicalId: string;
  normalizedText: string;
  displayText: string;
  onRemove: () => void;
  onCreateGroup: (position: { x: number; y: number }) => void;
  canCreateGroup: boolean;
  isSplitTarget: boolean;
  isSplitActionHovered: boolean;
}

function DraggableTextChip({
  canonicalId,
  normalizedText,
  displayText,
  onRemove,
  onCreateGroup,
  canCreateGroup,
  isSplitTarget,
  isSplitActionHovered,
}: DraggableTextChipProps) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: textDndId(canonicalId, normalizedText),
    data: { type: "text", canonicalId, text: normalizedText, displayText },
  });

  return (
    <div
      ref={setNodeRef}
      className={`${textItemStyle}${isDragging ? ` ${textItemDraggingStyle}` : ""}${
        isSplitTarget
          ? ` ${
              isSplitActionHovered
                ? textItemConfirmingSplitStyle
                : textItemPendingSplitStyle
            }`
          : ""
      }`}
      onContextMenu={(event) => {
        if (!canCreateGroup) return;
        event.preventDefault();
        event.stopPropagation();
        onCreateGroup({ x: event.clientX, y: event.clientY });
      }}
    >
      <button
        type="button"
        className={css({
          cursor: "grab",
          color: "text.lighter",
          bg: "transparent",
          border: "none",
          display: "flex",
          flexShrink: "0",
          mt: "0.5",
          p: "0",
          "&:active": { cursor: "grabbing" },
          "&:hover": { color: "text.default" },
        })}
        aria-label="Arrastrar mención a otro grupo"
        {...attributes}
        {...listeners}
      >
        <DotsSixVertical size={14} />
      </button>
      <styled.span
        textStyle="label.md.default"
        flex="1"
        minW="0"
        wordBreak="break-word"
        overflowWrap="anywhere"
        whiteSpace="pre-wrap"
      >
        {displayText}
      </styled.span>
      <button
        type="button"
        className={css({
          cursor: "pointer",
          color: "text.lighter",
          bg: "transparent",
          border: "none",
          display: "flex",
          flexShrink: "0",
          alignSelf: "center",
          p: "0",
          "&:hover": { color: "text.default" },
        })}
        onClick={onRemove}
        aria-label={`Eliminar ${displayText}`}
      >
        <XCircle size={14} />
      </button>
    </div>
  );
}

function TextChipOverlay({ text }: { text: string }) {
  return (
    <div
      className={css({
        display: "flex",
        alignItems: "center",
        gap: "1",
        px: "2",
        py: "1",
        bg: "bg.primary-alternative",
        rounded: "xs",
        boxShadow: "[0_4px_12px_rgba(17,0,65,0.18)]",
        opacity: "0.92",
        cursor: "grabbing",
        pointerEvents: "none",
      })}
    >
      <DotsSixVertical size={14} />
      <styled.span textStyle="label.md.default">{text}</styled.span>
    </div>
  );
}

interface LabelEntityTabProps {
  expandedGroups: Record<string, boolean>;
  expandedSections: Record<string, boolean>;
  onDerivedGroupRemove: (canonicalId: string) => void;
  onDerivedValueRemove: (canonicalId: string, value: string) => void;
  onDerivedLabelChange: (
    canonicalId: string,
    labelId: string | undefined,
  ) => void;
  onGroupOpenChange: (canonicalId: string, open: boolean) => void;
  onSectionOpenChange: (section: string, open: boolean) => void;
}

export default function LabelEntityTab({
  expandedGroups,
  expandedSections,
  onDerivedGroupRemove,
  onDerivedValueRemove,
  onDerivedLabelChange,
  onGroupOpenChange,
  onSectionOpenChange,
}: LabelEntityTabProps) {
  const files = useFiles();
  const dispatch = useFileDispatch();
  const { tags, words } = useExcludedTagsConfig();
  const activeFiles = useMemo(
    () =>
      files.map((file) => ({
        ...file,
        predictions: filterActivePredictions(file.predictions, tags, words),
      })),
    [files, tags, words],
  );
  const groups = useEntityGroups(activeFiles);
  const {
    hoveredCanonicalId,
    lastEditedCanonicalId,
    setHoveredCanonicalId,
    setLastEditedCanonicalId,
  } = useHoverState();

  const { groupOrder } = useGroupOrder();
  const { setGroupOrder } = useGroupOrderActions();

  const [pendingRemoval, setPendingRemoval] = useState<{
    canonicalId: string;
    label: string;
  } | null>(null);
  const [pendingMerge, setPendingMerge] = useState<{
    source: EntityGroup;
    target: EntityGroup;
  } | null>(null);
  const [activeTextDrag, setActiveTextDrag] = useState<{
    normalizedText: string;
    displayText: string;
    fromCanonicalId: string;
  } | null>(null);
  const [overGroupId, setOverGroupId] = useState<string | null>(null);
  const [textMenu, setTextMenu] = useState<{
    x: number;
    y: number;
    canonicalId: string;
    normalizedText: string;
  } | null>(null);
  const [textMenuActionHovered, setTextMenuActionHovered] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );

  const groupsByCategory = useMemo(() => {
    const result: Record<string, EntityGroup[]> = Object.fromEntries(
      ANONYMIZER_CATEGORY_NAMES.map((c) => [c, []]),
    );
    for (const g of groups) {
      const cat = getAnonymizerCategoryForLabel(g.renderBase);
      result[cat] ??= [];
      result[cat].push(g);
    }
    return result;
  }, [groups]);

  useEffect(() => {
    if (!textMenu) return;

    const close = () => {
      setTextMenu(null);
      setTextMenuActionHovered(false);
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };

    window.addEventListener("click", close);
    window.addEventListener("contextmenu", close);
    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("scroll", close, true);

    return () => {
      window.removeEventListener("click", close);
      window.removeEventListener("contextmenu", close);
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("scroll", close, true);
    };
  }, [textMenu]);

  function getOrderedGroups(category: string): EntityGroup[] {
    const catGroups = groupsByCategory[category] ?? [];
    const order = groupOrder?.[category];
    if (!order) return catGroups;
    const byId = new Map(catGroups.map((g) => [g.canonicalId, g]));
    const ordered: EntityGroup[] = [];
    for (const id of order) {
      const g = byId.get(id);
      if (g) {
        ordered.push(g);
        byId.delete(id);
      }
    }
    for (const g of byId.values()) ordered.push(g);
    return ordered;
  }

  function handleDragStart(event: DragStartEvent) {
    const data = event.active.data.current;
    if (data?.type === "text") {
      setActiveTextDrag({
        normalizedText: data.text,
        displayText: data.displayText ?? data.text,
        fromCanonicalId: data.canonicalId,
      });
    }
  }

  function handleDragOver(event: DragOverEvent) {
    if (!activeTextDrag) {
      setOverGroupId(null);
      return;
    }
    const overId = event.over?.id as string | undefined;
    if (!overId) {
      setOverGroupId(null);
      return;
    }
    const groupId =
      parseGroupDndId(overId) ?? parseTextDndId(overId)?.canonicalId ?? null;
    setOverGroupId(groupId);
  }

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    setActiveTextDrag(null);
    setOverGroupId(null);
    if (!over) return;

    const activeId = active.id as string;
    const overId = over.id as string;
    const textParsed = parseTextDndId(activeId);

    if (textParsed) {
      const targetCanonicalId =
        parseGroupDndId(overId) ?? parseTextDndId(overId)?.canonicalId ?? null;
      if (!targetCanonicalId || targetCanonicalId === textParsed.canonicalId)
        return;
      const sourceGroup = groups.find(
        (g) => g.canonicalId === textParsed.canonicalId,
      );
      const targetGroup = groups.find(
        (g) => g.canonicalId === targetCanonicalId,
      );
      if (!sourceGroup || !targetGroup) return;
      for (const mention of sourceGroup.mentions.filter(
        (m) => normalizeText(m.text) === normalizeText(textParsed.text),
      )) {
        dispatch(
          moveMentionToGroup(
            mention.mentionId,
            targetGroup.canonicalId,
            targetGroup.renderBase as AllLabels | AllLabelsWithSufix,
          ),
        );
      }
      setLastEditedCanonicalId(targetGroup.canonicalId);
      return;
    }

    const groupParsed = parseGroupDndId(activeId);
    if (groupParsed) {
      const targetCanonicalId = parseGroupDndId(overId);
      if (!targetCanonicalId || targetCanonicalId === groupParsed) return;
      const sourceGroup = groups.find((g) => g.canonicalId === groupParsed);
      if (!sourceGroup) return;
      const category = getAnonymizerCategoryForLabel(sourceGroup.renderBase);
      if (!category) return;
      const orderedGroups = getOrderedGroups(category);
      const ids = orderedGroups.map((g) => g.canonicalId);
      const oldIdx = ids.indexOf(groupParsed);
      const newIdx = ids.indexOf(targetCanonicalId);
      if (oldIdx === -1 || newIdx === -1) return;
      setGroupOrder({
        ...groupOrder,
        [category]: arrayMove(ids, oldIdx, newIdx),
      });
    }
  }

  function handleLabelChange(canonicalId: string, labelId: string | undefined) {
    if (!labelId) return;
    dispatch(
      updatePredictionsByCanonicalId(
        canonicalId,
        labelId as AllLabels | AllLabelsWithSufix,
      ),
    );
    onDerivedLabelChange(canonicalId, labelId);
    setLastEditedCanonicalId(canonicalId);
  }

  function handleRemoveValue(canonicalId: string, normalizedText: string) {
    dispatch(removePredictionValueByCanonicalId(canonicalId, normalizedText));
    onDerivedValueRemove(canonicalId, normalizedText);
  }

  function handleCreateGroupFromText() {
    if (!textMenu) return;

    const sourceGroup = groups.find(
      (group) => group.canonicalId === textMenu.canonicalId,
    );
    if (!sourceGroup) {
      setTextMenu(null);
      setTextMenuActionHovered(false);
      return;
    }

    const targetCanonicalId = crypto.randomUUID();
    const targetLabel = sourceGroup.renderBase as
      | AllLabels
      | AllLabelsWithSufix;
    const mentionsToSplit = sourceGroup.mentions.filter(
      (mention) => normalizeText(mention.text) === textMenu.normalizedText,
    );
    if (mentionsToSplit.length === 0) {
      setTextMenu(null);
      setTextMenuActionHovered(false);
      return;
    }

    for (const mention of mentionsToSplit) {
      dispatch(
        moveMentionToGroup(mention.mentionId, targetCanonicalId, targetLabel),
      );
    }

    const category = getAnonymizerCategoryForLabel(sourceGroup.renderBase);
    const existingOrder = groupOrder?.[category];
    if (existingOrder) {
      const sourceIndex = existingOrder.indexOf(sourceGroup.canonicalId);
      const nextOrder = existingOrder.filter((id) => id !== targetCanonicalId);
      nextOrder.splice(
        sourceIndex === -1 ? nextOrder.length : sourceIndex + 1,
        0,
        targetCanonicalId,
      );
      setGroupOrder({ ...groupOrder, [category]: nextOrder });
    }

    setLastEditedCanonicalId(targetCanonicalId);
    setTextMenu(null);
    setTextMenuActionHovered(false);
  }

  function confirmRemoval() {
    if (!pendingRemoval) return;
    dispatch(removePredictionsByCanonicalId(pendingRemoval.canonicalId));
    onDerivedGroupRemove(pendingRemoval.canonicalId);
    setPendingRemoval(null);
  }

  function confirmMerge() {
    if (!pendingMerge) return;
    dispatch(
      mergeGroups(
        pendingMerge.source.canonicalId,
        pendingMerge.target.canonicalId,
        pendingMerge.target.renderBase as AllLabels | AllLabelsWithSufix,
      ),
    );
    setPendingMerge(null);
    setLastEditedCanonicalId(null);
  }

  return (
    <>
      <RemoveDialog
        isOpen={pendingRemoval !== null}
        label={pendingRemoval?.label ?? ""}
        onClose={(open) => {
          if (!open) setPendingRemoval(null);
        }}
        onConfirm={confirmRemoval}
      />
      <MergeDialog
        source={pendingMerge?.source ?? null}
        target={pendingMerge?.target ?? null}
        onClose={() => setPendingMerge(null)}
        onConfirm={confirmMerge}
      />

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragEnd={handleDragEnd}
      >
        {textMenu && (
          <div
            className={textContextMenu}
            style={{ left: textMenu.x, top: textMenu.y }}
            onClick={(event) => event.stopPropagation()}
            onContextMenu={(event) => {
              event.preventDefault();
              event.stopPropagation();
            }}
            onPointerEnter={() => setTextMenuActionHovered(true)}
            onPointerLeave={() => setTextMenuActionHovered(false)}
          >
            <button
              type="button"
              className={textContextMenuButton}
              onClick={handleCreateGroupFromText}
            >
              <PlusCircle size={14} />
              Crear nuevo grupo
            </button>
          </div>
        )}

        <Stack gap="4">
          {ANONYMIZER_CATEGORY_NAMES.map((category, i) => {
            const orderedGroups = getOrderedGroups(category);
            if (orderedGroups.length === 0) return null;
            const labelOptions = getLabelsPrioritizingCategory(category);

            return (
              <Stack key={category} gap="4">
                {i > 0 && <styled.hr borderColor="[#BCBAB8]" />}
                <LabelManagerSection
                  title={category}
                  open={expandedSections[category] ?? true}
                  onOpenChange={(open) => onSectionOpenChange(category, open)}
                >
                  <Stack gap="2">
                    <SortableContext
                      items={orderedGroups.map((g) =>
                        groupDndId(g.canonicalId),
                      )}
                      strategy={verticalListSortingStrategy}
                    >
                      {orderedGroups.map((group) => {
                        const isDropTarget =
                          activeTextDrag !== null &&
                          overGroupId === group.canonicalId;
                        const duplicatePrimary = group.duplicateOf
                          ? groups.find(
                              (g) => g.canonicalId === group.duplicateOf,
                            )
                          : null;

                        // When the user recently edited THIS group and it became a primary with a
                        // duplicate pointing to it, show the badge on this group instead.
                        const reverseDuplicate =
                          !group.isDuplicate &&
                          group.canonicalId === lastEditedCanonicalId
                            ? (groups.find(
                                (g) =>
                                  g.isDuplicate &&
                                  g.duplicateOf === group.canonicalId,
                              ) ?? null)
                            : null;
                        const badgeTarget =
                          reverseDuplicate ?? duplicatePrimary;
                        const isGroupOpen =
                          expandedGroups[group.canonicalId] ?? true;

                        return (
                          <SortableGroup
                            key={group.canonicalId}
                            id={groupDndId(group.canonicalId)}
                            isOpen={isGroupOpen}
                            onToggleOpen={() =>
                              onGroupOpenChange(group.canonicalId, !isGroupOpen)
                            }
                            toggleLabel={
                              isGroupOpen
                                ? `Colapsar ${group.renderToken}`
                                : `Expandir ${group.renderToken}`
                            }
                          >
                            <Stack
                              gap="1.5"
                              p="2"
                              className={`${groupCardStyle}${isDropTarget || hoveredCanonicalId === group.canonicalId ? ` ${groupHoverStyle}` : ""}`}
                              onMouseEnter={() =>
                                setHoveredCanonicalId(group.canonicalId)
                              }
                              onMouseLeave={() => setHoveredCanonicalId(null)}
                            >
                              <div className={groupHeader}>
                                <div className={groupHeaderLeft}>
                                  {badgeTarget && (
                                    <TooltipProvider>
                                      <Tooltip>
                                        <TooltipTrigger asChild>
                                          <button
                                            type="button"
                                            className={duplicateBadge}
                                            onClick={() => {
                                              if (reverseDuplicate) {
                                                setPendingMerge({
                                                  source: reverseDuplicate,
                                                  target: group,
                                                });
                                              } else if (duplicatePrimary) {
                                                setPendingMerge({
                                                  source: group,
                                                  target: duplicatePrimary,
                                                });
                                              }
                                            }}
                                          >
                                            <Warning size={11} weight="bold" />
                                            <ArrowsLeftRight size={10} />
                                            <span>
                                              {badgeTarget.renderToken}
                                            </span>
                                          </button>
                                        </TooltipTrigger>
                                        <TooltipContent
                                          showArrow={false}
                                          className={css({
                                            bg: "action.hover",
                                            color: "white",
                                            px: "1.5",
                                            py: "0.5",
                                            rounded: "sm",
                                            fontSize: "[12px]",
                                            boxShadow: "[none]",
                                          })}
                                        >
                                          Grupo idéntico a{" "}
                                          {badgeTarget.renderToken}. Clic para
                                          unificar.
                                        </TooltipContent>
                                      </Tooltip>
                                    </TooltipProvider>
                                  )}
                                </div>
                                <span
                                  className={suffixBadge}
                                  title={`Token: ${group.renderToken}`}
                                >
                                  {group.renderToken}
                                </span>
                              </div>

                              <HStack gap="1" alignItems="center" minW="0">
                                <div
                                  className={css({
                                    flex: "1",
                                    minW: "0",
                                    overflow: "hidden",
                                  })}
                                >
                                  <AnonymizerLabelSelect
                                    size="sm"
                                    options={labelOptions}
                                    placeholder="Seleccionar entidad"
                                    value={group.renderBase}
                                    currentCategory={category}
                                    onChange={(opt) =>
                                      handleLabelChange(
                                        group.canonicalId,
                                        opt.id,
                                      )
                                    }
                                  />
                                </div>
                                <button
                                  type="button"
                                  className={iconButton}
                                  onClick={() =>
                                    setPendingRemoval({
                                      canonicalId: group.canonicalId,
                                      label: group.renderBase,
                                    })
                                  }
                                  aria-label="Eliminar grupo"
                                >
                                  <Trash size={16} />
                                </button>
                              </HStack>

                              {isGroupOpen && (
                                <Stack
                                  gap="1"
                                  align="stretch"
                                  bg="bg.secondary"
                                  p="1"
                                  rounded="xs"
                                  minH="6"
                                >
                                  {group.uniqueTexts.flatMap((normText, idx) =>
                                    group.displayTexts[idx].map((verbatim) => (
                                      <DraggableTextChip
                                        key={`${normText}:${verbatim}`}
                                        canonicalId={group.canonicalId}
                                        normalizedText={normText}
                                        displayText={verbatim}
                                        onRemove={() =>
                                          handleRemoveValue(
                                            group.canonicalId,
                                            normText,
                                          )
                                        }
                                        canCreateGroup={
                                          group.mentions.length > 1
                                        }
                                        onCreateGroup={(position) => {
                                          setTextMenu({
                                            ...position,
                                            canonicalId: group.canonicalId,
                                            normalizedText: normText,
                                          });
                                          setTextMenuActionHovered(false);
                                        }}
                                        isSplitTarget={
                                          textMenu?.canonicalId ===
                                            group.canonicalId &&
                                          textMenu.normalizedText === normText
                                        }
                                        isSplitActionHovered={
                                          textMenuActionHovered
                                        }
                                      />
                                    )),
                                  )}
                                  {group.uniqueTexts.length === 0 && (
                                    <styled.p
                                      textStyle="label.sm.default"
                                      color="text.lighter"
                                      px="1"
                                      py="0.5"
                                      fontStyle="italic"
                                    >
                                      Sin menciones
                                    </styled.p>
                                  )}
                                </Stack>
                              )}
                            </Stack>
                          </SortableGroup>
                        );
                      })}
                    </SortableContext>
                  </Stack>
                </LabelManagerSection>
              </Stack>
            );
          })}
        </Stack>

        <DragOverlay dropAnimation={null}>
          {activeTextDrag && (
            <TextChipOverlay text={activeTextDrag.displayText} />
          )}
        </DragOverlay>
      </DndContext>
    </>
  );
}
