import { LabelDecisiones, type LabelType } from "@/types/aymurai";
import nArray from "@/utils/nArray";
import { useRef, useState } from "react";
import type { FormData, RegisterFunction, SubmitFunction } from "./types";

/**
 * Creates a group of component references and a function to handle
 * @param initialDecisiones Initial amount of decisiones
 * @returns `register()` and `submit()` functions
 */
export default function useForm(initialDecisiones = 1) {
  // Create an n-array of empty objects
  const refs = useRef<FormData>({ DECISIONES: nArray(initialDecisiones, {}) });
  // State containing decisionAmounts. This is done in this way to make React perform a re-render
  // in case we want to add a decision
  const [decisionAmount, setDecisionAmount] = useState(initialDecisiones);

  /**
   * Adds a reference to a components value to the 'state'
   * @param name Name of the reference
   * @returns A `(ref) => void` function that should be applied to the `ref={...}` prop of a component
   */
  const register: RegisterFunction = (name, decision) => (ref) => {
    if (ref) {
      // We have to alter the DECISIONES array
      if (name in LabelDecisiones) {
        // In case we already have an array, modify the label
        if (refs.current.DECISIONES) {
          const arr = refs.current.DECISIONES;
          const i = decision ?? 0;

          arr[i][name as LabelDecisiones] = ref.value;
        } else {
          // We have no array, create it
          refs.current.DECISIONES = [{ [name]: ref.value }];
        }
      } else {
        // Just modify the label in the object
        refs.current[name as LabelType] = ref.value;
      }
    }
  };

  /**
   * Collects all the data from the referrences and creates a submit function with them
   * @param callback Callback that is called with all the data collected from the references as an argument
   * @returns A `(event) => void` function that should be applied to the `onSubmit={...}` prop of a form
   */
  const submit = (callback: SubmitFunction) => () => {
    callback(refs.current);
  };

  const addDecision = () => {
    const arr = refs.current.DECISIONES;

    if (arr) {
      setDecisionAmount((dec) => dec + 1);
      refs.current.DECISIONES = [...arr, {}];
    } else {
      setDecisionAmount(1);
      refs.current.DECISIONES = [{}];
    }
  };

  const getDecisionValue = (n: number) => (field: LabelDecisiones) => {
    const arr = refs.current.DECISIONES;

    if (arr && n in arr && field in arr[n]) {
      return arr[n][field];
    }
    return "";
  };

  return {
    register,
    submit,
    addDecision,
    decisionAmount,
    getDecisionValue,
  };
}

export * from "./types";
