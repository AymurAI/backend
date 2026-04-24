import { Input, Select, ValidationForm } from "@/components";
import { LabelType } from "@/types/aymurai";
import type { FormProps } from "../FormGroup.types";
import json from "./options.json";

export default function DatosDenunciante({
  onSubmit,
  onCheck,
  register,
  suggester,
}: FormProps) {
  return (
    <ValidationForm
      title="Datos del denunciante"
      onSubmit={onSubmit}
      onCheck={onCheck}
    >
      <Select
        ref={register(LabelType.GENERO_DENUNCIANTE)}
        {...suggester.select(LabelType.GENERO_DENUNCIANTE)}
        label="Género"
        options={json.GENERO}
      />

      <Select
        ref={register(LabelType.NACIONALIDAD_DENUNCIANTE)}
        {...suggester.select(LabelType.NACIONALIDAD_DENUNCIANTE)}
        label="Nacionalidad"
        options={json.NACIONALIDAD}
      />
      <Input
        ref={register(LabelType.EDAD_DENUNCIANTE)}
        {...suggester.text(LabelType.EDAD_DENUNCIANTE)}
        label="Edad"
        helper="Al momento del hecho"
        type="number"
      />
      <Select
        ref={register(LabelType.NIVEL_INSTRUCCION_DENUNCIANTE)}
        {...suggester.select(LabelType.NIVEL_INSTRUCCION_DENUNCIANTE)}
        label="Nivel de instrucción"
        options={json.NIVEL_INSTRUCCION}
      />
    </ValidationForm>
  );
}
