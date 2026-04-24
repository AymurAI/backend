import { useEffect, useState } from "react";

import { DecisionTabs } from "@/components";
import { useFileDispatch, useForm } from "@/hooks";
import { appendValidation } from "@/reducers/file/actions";
import type { DocFile } from "@/types/file";
import { Suggester, countDecisiones } from "@/utils/predictions";
import Container from "./FormGroup.styles";
import {
  DatosAcusado,
  DatosDenunciante,
  Decision,
  InfoGral,
  InfoHecho,
} from "./forms";

interface Props {
  file: DocFile;
  onCheck: (checked: boolean) => void;
}
export default function FormGroup({ file, onCheck }: Props) {
  const [decision, setDecision] = useState(0);

  const [checkedInfoGral, setCheckedInfoGral] = useState(false);
  const [checkedInfoHecho, setCheckedInfoHecho] = useState(false);
  const [checkedDecision, setCheckedDecision] = useState(false);
  const [checkedDatosDenunciante, setCheckedDatosDenunciante] = useState(false);
  const [checkedDatosAcusado, setCheckedDatosAcusado] = useState(false);

  const { register, submit, addDecision, decisionAmount, getDecisionValue } =
    useForm(countDecisiones(file.predictions));
  const dispatch = useFileDispatch();

  const createDecision = () => {
    addDecision();
  };
  const selectDecision = (n: number) => setDecision(n);

  const handleSubmit = submit((data) => {
    console.log({ data });
    dispatch(appendValidation(file.data.name, data));
  });

  const props = {
    register,
    onSubmit: handleSubmit,
    suggester: new Suggester(file.predictions),
  };
  const decisionProps = {
    ...props,
    getDecisionValue,
  };

  useEffect(() => {
    onCheck(
      checkedInfoGral &&
        checkedInfoHecho &&
        checkedDecision &&
        checkedDatosDenunciante &&
        checkedDatosAcusado,
    );
  }, [
    onCheck,
    checkedInfoGral,
    checkedInfoHecho,
    checkedDecision,
    checkedDatosDenunciante,
    checkedDatosAcusado,
  ]);

  return (
    <Container>
      <InfoGral {...props} onCheck={setCheckedInfoGral} />

      <DecisionTabs
        selected={decision}
        addDecision={createDecision}
        {...{ decisionAmount, selectDecision }}
      />
      <Container key={decision}>
        <InfoHecho
          {...decisionProps}
          decision={decision}
          onCheck={setCheckedInfoHecho}
        />
        <Decision
          {...decisionProps}
          decision={decision}
          onCheck={setCheckedDecision}
        />
      </Container>

      <DatosDenunciante {...props} onCheck={setCheckedDatosDenunciante} />
      <DatosAcusado {...props} onCheck={setCheckedDatosAcusado} />
    </Container>
  );
}
