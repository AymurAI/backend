import { Input, Select, ValidationForm } from "@/components";
import { LabelType } from "@/types/aymurai";
import type { FormProps } from "../FormGroup.types";
import json from "./options.json";

export default function DatosAcusado({
  onSubmit,
  onCheck,
  register,
  suggester,
}: FormProps) {
  return (
    <ValidationForm
      title="Datos del acusado/a"
      onSubmit={onSubmit}
      onCheck={onCheck}
    >
      <Select
        ref={register(LabelType.GENERO_ACUSADO)}
        {...suggester.select(LabelType.GENERO_ACUSADO)}
        label="Género"
        options={json.GENERO}
      />
      <Select
        ref={register(LabelType.PERSONA_ACUSADA_NO_DETERMINADA)}
        {...suggester.select(LabelType.PERSONA_ACUSADA_NO_DETERMINADA)}
        label="Persona acusada no determinada"
        options={json.PERSONA_ACUSADA_NO_DETERMINADA}
      />
      <Select
        ref={register(LabelType.NACIONALIDAD_ACUSADO)}
        {...suggester.select(LabelType.NACIONALIDAD_ACUSADO)}
        label="Nacionalidad"
        options={json.NACIONALIDAD}
      />
      <Input
        ref={register(LabelType.EDAD_ACUSADO)}
        {...suggester.text(LabelType.EDAD_ACUSADO)}
        type="number"
        label="Edad"
        helper="Al momento del hecho"
      />
      <Select
        ref={register(LabelType.NIVEL_INSTRUCCION_ACUSADO)}
        {...suggester.select(LabelType.NIVEL_INSTRUCCION_ACUSADO)}
        label="Nivel de instrucción"
        options={json.NIVEL_INSTRUCCION}
      />
    </ValidationForm>
  );
}
