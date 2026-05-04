import Button from "@/components/ui/button";
import { useFiles } from "@/hooks";
import { css } from "@/styled/css";
import { HStack, Stack, styled } from "@/styled/jsx";
import { anonymizerLabels } from "@/types/aymurai";
import { Trash, XCircle } from "phosphor-react";
import { useMemo, useState } from "react";

import Select from "@/components/ui/select";
import { Label } from "./label";
import RemoveDialog from "./remove-dialog";
import LabelManagerSection from "./section";

// ─── Category config ────────────────────────────────────────────────────────

const categoryConfig: Record<
  string,
  { labelIds: string[]; placeholder: string }
> = {
  Roles: {
    placeholder: "Seleccionar Rol",
    labelIds: [
      "PER",
      "USUARIX",
      "DENUNCIANTE",
      "ACUSADO/A",
      "TESTIGO/A",
      "NINO/A_ADOSLECENTE",
    ],
  },
  Lugares: {
    placeholder: "Seleccionar Lugar",
    labelIds: ["DIRECCION", "LOC"],
  },
  Documentos: {
    placeholder: "Seleccionar Tipo de Documento",
    labelIds: [
      "DNI",
      "AFILIADO",
      "CAUSA",
      "CUIJ",
      "CUIT_CUIL",
      "CBU",
      "NUM_ACTUACION",
      "NUM_CAJA_AHORRO",
      "NUM_EXPEDIENTE",
      "NUM_MATRICULA",
      "PATENTE_DOMINIO",
    ],
  },
  "Otra entidad": {
    placeholder: "Seleccionar",
    labelIds: [
      "TEL",
      "CORREO_ELECTRÓNICO",
      "BANCO",
      "INSTITUCION",
      "EDAD",
      "ESTUDIOS",
      "FECHA",
      "LINK",
      "MARCA_AUTOMOVIL",
      "NACIONALIDAD",
      "TEXTO_ANONIMIZAR",
    ],
  },
};

const categories = Object.keys(categoryConfig);

// Reverse lookup: labelId → category name
const labelToCategory: Record<string, string> = {};
for (const [cat, { labelIds }] of Object.entries(categoryConfig)) {
  for (const id of labelIds) {
    labelToCategory[id] = cat;
  }
}

// ─── State types ─────────────────────────────────────────────────────────────

interface DerivedGroup {
  canonicalId: string;
  labelId: string;
  values: string[];
}

interface ManualGroup {
  id: string;
  selectedLabelId: string | undefined;
  values: string[];
}

type ManualCategoryGroups = Record<string, ManualGroup[]>;

const initialManualGroups = (): ManualCategoryGroups =>
  Object.fromEntries(categories.map((cat) => [cat, []]));

// ─── Styles ──────────────────────────────────────────────────────────────────

const valueItem = css({
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  px: "3",
  py: "2",
  bg: "bg.primary-alternative",
  p: "1",
  rounded: "sm",
  textStyle: "label.md.default",
  color: "text.default",
});

const iconButton = css({
  cursor: "pointer",
  color: "text.lighter",
  bg: "transparent",
  border: "none",
  display: "flex",
  alignItems: "center",
  p: "0",
  "&:hover": { color: "text.default" },
});

interface LabelEntityTabProps {
  onDerivedGroupRemove: (canonicalId: string) => void;
  onDerivedValueRemove: (canonicalId: string, value: string) => void;
  onDerivedLabelChange: (
    canonicalId: string,
    labelId: string | undefined,
  ) => void;
}
export default function LabelEntityTab({
  onDerivedGroupRemove,
  onDerivedValueRemove,
  onDerivedLabelChange,
}: LabelEntityTabProps) {
  const files = useFiles();
  const [manualGroups, setManualGroups] =
    useState<ManualCategoryGroups>(initialManualGroups);
  const [removedDerivedIds, setRemovedDerivedIds] = useState<string[]>([]);
  const [removedDerivedValues, setRemovedDerivedValues] = useState<
    Record<string, string[]>
  >({});
  const [overriddenDerivedLabels, setOverriddenDerivedLabels] = useState<
    Record<string, string | undefined>
  >({});

  const [pendingRemoval, setPendingRemoval] = useState<
    | { kind: "derived"; canonicalId: string; label: string }
    | { kind: "manual"; category: string; groupId: string; label: string }
    | null
  >(null);

  // Derive groups from predictions, merging by canonical_entity_id
  const derivedGroups = useMemo(() => {
    const result: Record<string, DerivedGroup[]> = Object.fromEntries(
      categories.map((cat) => [cat, []]),
    );
    const byCanonicalId = new Map<string, DerivedGroup>();

    for (const file of files) {
      for (const pred of file.predictions ?? []) {
        const { canonical_entity_id, aymurai_label } = pred.attrs;
        if (!canonical_entity_id) continue;

        const baseLabel = aymurai_label.replace(/_\d+$/, "");
        const category = labelToCategory[baseLabel];
        if (!category) continue;

        if (byCanonicalId.has(canonical_entity_id)) {
          const group = byCanonicalId.get(canonical_entity_id)!;
          if (!group.values.includes(pred.text)) {
            group.values.push(pred.text);
          }
        } else {
          const group: DerivedGroup = {
            canonicalId: canonical_entity_id,
            labelId: baseLabel,
            values: [pred.text],
          };
          byCanonicalId.set(canonical_entity_id, group);
          result[category].push(group);
        }
      }
    }

    return result;
  }, [files]);

  const confirmRemoval = () => {
    if (!pendingRemoval) return;
    if (pendingRemoval.kind === "derived") {
      setRemovedDerivedIds((prev) => [...prev, pendingRemoval.canonicalId]);
      onDerivedGroupRemove?.(pendingRemoval.canonicalId);
    } else {
      removeManualGroup(pendingRemoval.category, pendingRemoval.groupId);
    }
    setPendingRemoval(null);
  };

  const removeDerivedValue = (canonicalId: string, value: string) => {
    setRemovedDerivedValues((prev) => ({
      ...prev,
      [canonicalId]: [...(prev[canonicalId] ?? []), value],
    }));
    onDerivedValueRemove?.(canonicalId, value);
  };

  const changeDerivedLabel = (
    canonicalId: string,
    labelId: string | undefined,
  ) => {
    setOverriddenDerivedLabels((prev) => ({ ...prev, [canonicalId]: labelId }));
    onDerivedLabelChange?.(canonicalId, labelId);
  };

  const addManualGroup = (category: string) => {
    setManualGroups((prev) => ({
      ...prev,
      [category]: [
        ...prev[category],
        { id: crypto.randomUUID(), selectedLabelId: undefined, values: [] },
      ],
    }));
  };

  const removeManualGroup = (category: string, groupId: string) => {
    setManualGroups((prev) => ({
      ...prev,
      [category]: prev[category].filter((g) => g.id !== groupId),
    }));
  };

  const setManualGroupLabel = (
    category: string,
    groupId: string,
    labelId: string | undefined,
  ) => {
    setManualGroups((prev) => ({
      ...prev,
      [category]: prev[category].map((g) =>
        g.id === groupId ? { ...g, selectedLabelId: labelId } : g,
      ),
    }));
  };

  const removeManualValue = (
    category: string,
    groupId: string,
    value: string,
  ) => {
    setManualGroups((prev) => ({
      ...prev,
      [category]: prev[category].map((g) =>
        g.id === groupId
          ? { ...g, values: g.values.filter((v) => v !== value) }
          : g,
      ),
    }));
  };

  return (
    <>
    <RemoveDialog
      isOpen={pendingRemoval !== null}
      label={pendingRemoval?.label ?? ""}
      onClose={(open) => { if (!open) setPendingRemoval(null); }}
      onConfirm={confirmRemoval}
    />
    <Stack gap="6">
      {categories.map((category, i) => {
        const { labelIds, placeholder } = categoryConfig[category];
        const options = anonymizerLabels.filter((l) => labelIds.includes(l.id));
        const categoryDerived = derivedGroups[category];
        const categoryManual = manualGroups[category];

        return (
          <>
            {i > 0 && (
              <styled.hr borderColor="[#BCBAB8]" key={`hr-${category}`} />
            )}
            <LabelManagerSection key={category} title={category}>
              <Stack gap="4">
                {categoryDerived
                  .filter((g) => !removedDerivedIds.includes(g.canonicalId))
                  .map((group) => {
                    const visibleValues = group.values.filter(
                      (v) =>
                        !(
                          removedDerivedValues[group.canonicalId] ?? []
                        ).includes(v),
                    );
                    const selectedLabel =
                      overriddenDerivedLabels[group.canonicalId] ??
                      group.labelId;
                    return (
                      <Stack key={group.canonicalId} gap="2">
                        <HStack gap="2" alignItems="center">
                          <Select
                            options={options}
                            placeholder={placeholder}
                            value={selectedLabel}
                            onChange={(opt) =>
                              changeDerivedLabel(group.canonicalId, opt.id)
                            }
                          />
                          <button
                            type="button"
                            className={iconButton}
                            onClick={() =>
                              setPendingRemoval({
                                kind: "derived",
                                canonicalId: group.canonicalId,
                                label: selectedLabel,
                              })
                            }
                            aria-label="Eliminar grupo"
                          >
                            <Trash size={20} />
                          </button>
                        </HStack>
                        <Stack
                          gap="1"
                          align="stretch"
                          bg="white"
                          p="1"
                          rounded="sm"
                        >
                          {visibleValues.map((value) => (
                            <Label
                              key={value}
                              onRemove={() =>
                                removeDerivedValue(group.canonicalId, value)
                              }
                            >
                              {value}
                            </Label>
                          ))}
                        </Stack>
                      </Stack>
                    );
                  })}

                {categoryManual.map((group) => (
                  <Stack key={group.id} gap="2">
                    <HStack gap="2" alignItems="center">
                      <Select
                        options={options}
                        placeholder={placeholder}
                        value={group.selectedLabelId}
                        onChange={(opt) =>
                          setManualGroupLabel(category, group.id, opt.id)
                        }
                      />
                      <button
                        type="button"
                        className={iconButton}
                        onClick={() =>
                          setPendingRemoval({
                            kind: "manual",
                            category,
                            groupId: group.id,
                            label: group.selectedLabelId ?? placeholder,
                          })
                        }
                        aria-label="Eliminar grupo"
                      >
                        <Trash size={20} />
                      </button>
                    </HStack>

                    {group.values.map((value) => (
                      <div key={value} className={valueItem}>
                        <span>{value}</span>
                        <button
                          type="button"
                          className={iconButton}
                          onClick={() =>
                            removeManualValue(category, group.id, value)
                          }
                          aria-label={`Eliminar ${value}`}
                        >
                          <XCircle size={18} />
                        </button>
                      </div>
                    ))}
                  </Stack>
                ))}

                <Button
                  variant="secondary"
                  onClick={() => addManualGroup(category)}
                >
                  Añadir
                </Button>
              </Stack>
            </LabelManagerSection>
          </>
        );
      })}
    </Stack>
    </>
  );
}
