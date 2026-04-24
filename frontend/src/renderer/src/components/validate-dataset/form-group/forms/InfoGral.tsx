import { Input, ValidationForm } from "@/components";
import { LabelType } from "@/types/aymurai";
import type { FormProps } from "../FormGroup.types";

export default function InfoGral({
  onSubmit,
  onCheck,
  register,
  suggester,
}: FormProps) {
  return (
    <ValidationForm
      title="Información general"
      onSubmit={onSubmit}
      onCheck={onCheck}
    >
      <Input
        ref={register(LabelType.N)}
        {...suggester.text(LabelType.N)}
        label="Número"
        type="number"
      />
      <Input
        ref={register(LabelType.NRO_REGISTRO)}
        {...suggester.text(LabelType.NRO_REGISTRO)}
        specialCharacters="bis"
        label="Número de registro"
        type="number"
      />
      <Input
        ref={register(LabelType.TOMO)}
        {...suggester.text(LabelType.TOMO)}
        label="Tomo"
        type="number"
      />
      <Input
        ref={register(LabelType.FECHA_RESOLUCION)}
        {...suggester.text(LabelType.FECHA_RESOLUCION)}
        label="Fecha de resolución"
      />
      <Input
        ref={register(LabelType.N_EXPTE_EJE)}
        {...suggester.text(LabelType.N_EXPTE_EJE)}
        specialCharacters="-_/"
        label="Nro de expediente"
        type="number"
      />
      <Input
        ref={register(LabelType.FIRMA)}
        {...suggester.text(LabelType.FIRMA)}
        label="Firma"
      />
    </ValidationForm>
  );
}
