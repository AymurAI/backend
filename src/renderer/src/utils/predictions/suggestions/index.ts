import type { SelectOption } from "@/components/select";
import {
  type AllLabels,
  type AllLabelsWithSufix,
  LabelDecisiones,
  type PredictLabel,
} from "@/types/aymurai";
import type {
  BooleanSuggestion,
  InputSuggestion,
  Prediction,
  PropertyCallback,
  SelectSuggestion,
} from "./types";

export default class Suggester {
  constructor(predictions: PredictLabel[] | undefined) {
    this.predictions = predictions ?? [];
  }

  // ------------
  // FIELDS
  // ------------
  private predictions: PredictLabel[];

  // ------------
  // PRIVATE METHODS
  // ------------
  /**
   * Transforms the predictions array into a { [label]: T } form to be used on the getters methods
   * @param propertyCallback This function is used to define which property is added when reducing
   * @returns A predictions array transformed into { [label]: T }
   */
  private reducePredictions<T>(
    propertyCallback: PropertyCallback<T>,
  ): Prediction<T> {
    const reduced = this.predictions.reduce(
      (prev, pred) => ({
        ...prev,
        // Append the next value
        [pred.attrs.aymurai_label]: propertyCallback(pred),
      }),
      {},
    );

    return reduced;
  }

  // ------------
  // PUBLIC METHODS
  // ------------
  /**
   * Searches for a suggestion for the given label
   * @param label Label to check
   * @returns The suggestion in `string | undefined` format
   */
  public text(label: AllLabels | AllLabelsWithSufix): InputSuggestion {
    const reduced = this.reducePredictions((pred) => pred.text);

    return {
      suggestion: reduced[label],
    };
  }

  /**
   * Searches for a suggestion option for the given label
   * @param label Label to check
   * @returns The suggestion as a `SelectOption` object
   */
  public select(label: AllLabels | AllLabelsWithSufix): SelectSuggestion {
    const reduced = this.reducePredictions((pred) => ({
      subclass: pred.attrs.aymurai_label_subclass ?? [],
      text: pred.text,
    }));

    const { subclass, text } = reduced[label] ?? {};

    const hasElements = !!subclass && !!subclass.length;
    const suggestion: SelectOption | undefined =
      hasElements && text ? { id: subclass[0], text } : undefined;

    return {
      priorityOrder: subclass,
      suggestion,
    };
  }

  /**
 * @example
 *[{
    ...
    "text": "violencia de género",
    "attrs": {
      ...
      "aymurai_label": "VIOLENCIA_DE_GENERO",
      "aymurai_label_subclass": [],
    }
  }]
 */
  violencia_genero(type: "si" | "no"): BooleanSuggestion {
    const reduced = this.reducePredictions((pred) => pred.text);

    const value = reduced[LabelDecisiones.VIOLENCIA_DE_GENERO];

    if (value !== undefined) {
      // Return true or false
      return { checked: type === "si" ? !!value : !value };
    }
    return { checked: undefined };
  }

  /**
 * @example
 * [{
 *  ...
    "text": "violencia económica y física",
    "attrs": {
      "aymurai_label": "VIOLENCIA_DE_GENERO",
      "aymurai_label_subclass": [
        "economica",
        "fisica"
      ],
    }
  }]
 */
  violencia_tipo(label: LabelDecisiones): BooleanSuggestion {
    // Reduce the predictions, merging VIOLENCIA_DE_GENERO subclasses
    const subclasses = this.predictions.reduce<string[]>((prev, pred) => {
      const label = pred.attrs.aymurai_label;
      const subclass = pred.attrs.aymurai_label_subclass;

      if (label === LabelDecisiones.VIOLENCIA_DE_GENERO && subclass) {
        return [...prev, ...subclass];
      }
      return prev;
    }, []);

    const values: Partial<Record<LabelDecisiones, string>> = {
      [LabelDecisiones.V_AMB]: "ambiental",
      [LabelDecisiones.V_ECON]: "economica",
      [LabelDecisiones.V_SIMB]: "simbolica",
      [LabelDecisiones.V_SEX]: "sexual",
      [LabelDecisiones.V_PSIC]: "psicologica",
      [LabelDecisiones.V_POLIT]: "politica",
      [LabelDecisiones.V_FISICA]: "fisica",
      [LabelDecisiones.V_SOC]: "social",
    };

    // Type of VIOLENCIA_TIPO
    const labelValue = values[label];

    return {
      // Find the desired type on the subclass array
      checked: !!subclasses.find((s) => s === labelValue),
    };
  }

  art_infringido(): SelectSuggestion {
    const reduced = this.reducePredictions(({ text }) => ({ id: text, text }));

    const suggestion = reduced[LabelDecisiones.ART_INFRINGIDO];

    if (suggestion) {
      return {
        priorityOrder: [suggestion.id],
        suggestion,
      };
    }

    return {
      suggestion: undefined,
      priorityOrder: undefined,
    };
  }
  codigo_o_ley(): SelectSuggestion {
    const reduced = this.reducePredictions(
      (pred) => pred.attrs.aymurai_label_subclass,
    );

    const suggestion = reduced[LabelDecisiones.ART_INFRINGIDO];

    if (suggestion) {
      return {
        suggestion: { id: suggestion[0] },
        priorityOrder: [suggestion[0]],
      };
    }

    return {
      suggestion: undefined,
      priorityOrder: undefined,
    };
  }

  decision(): SelectSuggestion {
    const reduced = this.reducePredictions(
      ({ attrs }) => attrs.aymurai_label_subclass ?? [],
    );

    const suggestion = reduced[LabelDecisiones.DECISION];

    return {
      priorityOrder: undefined,
      suggestion: suggestion ? { id: suggestion[0] } : undefined,
    };
  }
}
