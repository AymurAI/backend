import { Stack } from "@/components";
import { useLocation } from "@tanstack/react-router";
import Step from "./Step";
import { getStep } from "./utils";

/**
 * Stepper representing the current state of file validation
 * @param currentStep Current file validation step, between 0 and 4 (0 being validation process hasn't started)
 */
export default function Stepper() {
  const location = useLocation();
  const currentStep = getStep(location);

  // step = 0 is used in the case we want to hide the stepper (for example, in Onboarding page)
  if (currentStep === 0) return null;

  return (
    <Stack spacing="m">
      {/* STEP 1 */}
      <Step step={1} currentStep={currentStep}>
        Previsualización
      </Step>
      {/* STEP 2 */}
      <Step step={2} currentStep={currentStep}>
        Procesamiento
      </Step>
      {/* STEP 3 */}
      <Step step={3} currentStep={currentStep}>
        Validación
      </Step>
      {/* STEP 4 */}
      <Step step={4} currentStep={currentStep}>
        Finalización
      </Step>
    </Stack>
  );
}
