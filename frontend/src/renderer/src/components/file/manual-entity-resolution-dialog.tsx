import { useEffect, useMemo, useState } from "react";

import Button from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from "@/components/ui/dialog";
import Select from "@/components/ui/select";
import { css } from "@/styled/css";
import { Stack, styled } from "@/styled/jsx";
import type {
  ManualEntityResolution,
  SimilarEntityGroupCandidate,
} from "@/utils/anonymizer/entity-similarity";

export interface ManualEntityResolutionRequest {
  text: string;
  label: string;
  count: number;
  candidates: SimilarEntityGroupCandidate[];
}

interface ManualEntityResolutionDialogProps {
  request: ManualEntityResolutionRequest | null;
  onClose: () => void;
  onResolve: (resolution: ManualEntityResolution) => void;
}

const candidateSummary = css({
  bg: "bg.primary",
  border: "[1px solid #BCBAB8]",
  rounded: "sm",
  p: "2.5",
  display: "grid",
  gridTemplateColumns: "minmax(0, 1fr) max-content",
  alignItems: "center",
  columnGap: "3",
  rowGap: "0.5",
  minW: "0",
});

const candidateText = css({
  display: "grid",
  gap: "0.5",
  minW: "0",
});

const candidateToken = css({
  minW: "0",
  overflowWrap: "anywhere",
  wordBreak: "break-word",
});

const candidateReference = css({
  minW: "0",
  color: "text.default",
  overflowWrap: "anywhere",
  wordBreak: "break-word",
});

const candidateMeta = css({
  display: "grid",
  alignContent: "center",
  justifyItems: "end",
  gap: "0.5",
  justifySelf: "end",
  w: "[fit-content]",
  maxW: "full",
  px: "1.5",
  py: "0.5",
  bg: "[#E6E8FF]",
  color: "[#3F479D]",
  rounded: "xs",
  whiteSpace: "nowrap",
});

const categoryLabel = css({
  fontSize: "[11px]",
  fontWeight: "bold",
  lineHeight: "[1.2]",
});

const scoreValue = css({
  fontSize: "[11px]",
  fontWeight: "bold",
  lineHeight: "[1.2]",
});

function getCandidateLabel(candidate: SimilarEntityGroupCandidate) {
  const text = candidate.matchedText || "sin texto";
  return `${candidate.group.renderToken} - ${text} (${candidate.score}%)`;
}

export default function ManualEntityResolutionDialog({
  request,
  onClose,
  onResolve,
}: ManualEntityResolutionDialogProps) {
  const [selectedCanonicalId, setSelectedCanonicalId] = useState<string | null>(
    null,
  );

  useEffect(() => {
    setSelectedCanonicalId(request?.candidates[0]?.group.canonicalId ?? null);
  }, [request]);

  const candidate = useMemo(() => {
    if (!request) return null;
    return (
      request.candidates.find(
        (item) => item.group.canonicalId === selectedCanonicalId,
      ) ??
      request.candidates[0] ??
      null
    );
  }, [request, selectedCanonicalId]);

  const candidateOptions = useMemo(
    () =>
      request?.candidates.map((item) => ({
        id: item.group.canonicalId,
        text: getCandidateLabel(item),
      })) ?? [],
    [request],
  );

  const isLabelConflict = candidate ? !candidate.labelMatches : false;
  const selectedGroupText = candidate?.group.renderToken ?? "";
  const selectedGroupLabel = candidate?.group.renderBase ?? "";
  const mentionCount = request?.count ?? 0;

  return (
    <Dialog
      open={request !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent
        className={css({
          w: "[min(92vw, 520px)]",
          maxW: "[520px]",
          bg: "bg.secondary",
        })}
      >
        <DialogTitle>Resolver grupo de entidad</DialogTitle>
        {request && candidate && (
          <Stack gap="3" align="stretch">
            <DialogDescription>
              {isLabelConflict
                ? `Encontramos texto similar en otra categoría. Seleccionaste ${request.label} para "${request.text}".`
                : `Encontramos un grupo similar para "${request.text}".`}
            </DialogDescription>

            {request.candidates.length > 1 && (
              <Select
                label="Grupo sugerido"
                size="sm"
                value={candidate.group.canonicalId}
                options={candidateOptions}
                onChange={(option) => setSelectedCanonicalId(option.id)}
              />
            )}

            <div className={candidateSummary}>
              <div className={candidateText}>
                <styled.span
                  textStyle="label.md.strong"
                  className={candidateToken}
                >
                  {candidate.group.renderToken}
                </styled.span>
                <styled.span
                  textStyle="label.md.default"
                  className={candidateReference}
                >
                  {candidate.matchedText}
                </styled.span>
              </div>
              <div className={candidateMeta}>
                <span className={categoryLabel}>
                  {candidate.labelMatches
                    ? "Misma categoría"
                    : "Otra categoría"}
                </span>
                <span className={scoreValue}>
                  Similaridad {candidate.score}%
                </span>
              </div>
            </div>

            <styled.p textStyle="label.md.default" color="text.default">
              {mentionCount > 1
                ? `La decisión se aplicará a ${mentionCount} ocurrencias.`
                : "La decisión se aplicará a esta ocurrencia."}
            </styled.p>
          </Stack>
        )}
        <DialogFooter>
          {request && candidate && (
            <>
              <Button
                onClick={() => onResolve({ type: "existing", candidate })}
              >
                {isLabelConflict
                  ? `Agregar a ${selectedGroupText} y usar ${selectedGroupLabel}`
                  : `Agregar a ${selectedGroupText}`}
              </Button>
              <Button
                variant="secondary"
                onClick={() => onResolve({ type: "new" })}
              >
                Crear grupo nuevo {request.label}
              </Button>
            </>
          )}
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
