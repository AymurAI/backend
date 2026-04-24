import type { FormEventHandler } from "react";

import type { FormValue, RegisterFunction } from "@/hooks/useForm";
import type { LabelDecisiones } from "@/types/aymurai";
import type Suggester from "@/utils/predictions/suggestions";

export interface FormProps {
  decision?: number;
  register: RegisterFunction;
  onSubmit: FormEventHandler;
  onCheck: (checked: boolean) => void;
  suggester: Suggester;
}

export interface FormDecisionProps extends FormProps {
  getDecisionValue: (n: number) => (field: LabelDecisiones) => FormValue;
}
