import {
  Input,
  Radio,
  RadioGroup,
  Select,
  Stack,
  ValidationForm,
} from "@/components";
import { LabelDecisiones } from "@/types/aymurai";
import type { FormDecisionProps } from "../FormGroup.types";
import json from "./options.json";

export default function Decision({
  register,
  decision,
  onSubmit,
  onCheck,
  suggester,
  getDecisionValue,
}: FormDecisionProps) {
  const prop = (label: LabelDecisiones) => register(label, decision);

  const defaultValue = getDecisionValue(decision ?? 0);

  return (
    <ValidationForm title="Decisión/es" onSubmit={onSubmit} onCheck={onCheck}>
      <Select
        ref={prop(LabelDecisiones.TIPO_DE_RESOLUCION)}
        {...suggester.select(LabelDecisiones.TIPO_DE_RESOLUCION)}
        label="Tipo de la resolución"
        options={json.TIPO_DE_RESOLUCION}
        selected={defaultValue(LabelDecisiones.TIPO_DE_RESOLUCION) as string}
      />
      <Select
        ref={prop(LabelDecisiones.OBJETO_DE_LA_RESOLUCION)}
        {...suggester.select(LabelDecisiones.OBJETO_DE_LA_RESOLUCION)}
        options={json.OBJETO_DE_LA_RESOLUCION}
        label="Objeto de resolución"
        selected={
          defaultValue(LabelDecisiones.OBJETO_DE_LA_RESOLUCION) as string
        }
      />
      <Select
        ref={prop(LabelDecisiones.DETALLE)}
        {...suggester.select(LabelDecisiones.DETALLE)}
        label="Detalle"
        options={json.DETALLE}
        selected={defaultValue(LabelDecisiones.DETALLE) as string}
      />
      <Select
        ref={prop(LabelDecisiones.DECISION)}
        {...suggester.decision()}
        options={json.DECISION}
        label="Decisión"
        selected={defaultValue(LabelDecisiones.DECISION) as string}
      />
      <RadioGroup name="tipoAudiencia">
        <Radio
          // TODO gestionar este campo, debería depender de 'hora_inicio" y 'hora_cierre'
          // checked={
          //   getSuggestion(LabelDecisiones.TIPO_DE_AUDIENCIA_ORAL) === 'oral'
          // }
          ref={prop(LabelDecisiones.TIPO_DE_AUDIENCIA_ORAL)}
          checked={
            defaultValue(LabelDecisiones.TIPO_DE_AUDIENCIA_ORAL) as boolean
          }
        >
          Oral
        </Radio>
        <Radio
          // checked={
          //   getSuggestion(LabelDecisiones.TIPO_DE_AUDIENCIA_ESCRITA) ===
          //   'escrita'
          // }
          ref={prop(LabelDecisiones.TIPO_DE_AUDIENCIA_ESCRITA)}
          checked={
            defaultValue(LabelDecisiones.TIPO_DE_AUDIENCIA_ESCRITA) as boolean
          }
        >
          Escrita
        </Radio>
      </RadioGroup>
      {/* TODO ajustar posicionamiento de estos botones que se ponen en vertical cuando hay una sugerencia */}
      <Stack spacing="l" css={{ "&>*": { flex: 1 } }}>
        <Input
          ref={prop(LabelDecisiones.HORA_DE_INICIO)}
          {...suggester.text(LabelDecisiones.HORA_DE_INICIO)}
          label="Hora de inicio"
          defaultValue={defaultValue(LabelDecisiones.HORA_DE_INICIO) as string}
        />
        <Input
          ref={prop(LabelDecisiones.HORA_DE_CIERRE)}
          {...suggester.text(LabelDecisiones.HORA_DE_CIERRE)}
          label="Hora de cierre"
          defaultValue={defaultValue(LabelDecisiones.HORA_DE_CIERRE) as string}
        />
      </Stack>
      <Input
        ref={prop(LabelDecisiones.DURACION)}
        {...suggester.text(LabelDecisiones.DURACION)}
        label="Duración"
        defaultValue={defaultValue(LabelDecisiones.DURACION) as string}
      />
    </ValidationForm>
  );
}
