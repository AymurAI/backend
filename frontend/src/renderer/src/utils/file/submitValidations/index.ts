import type { DocFile } from "@/types/file";
import { validationToArray } from "@/utils/google";
import offline from "./offline";

interface Props {
  isOnline: boolean | undefined;
  validations: DocFile["validationObject"];
}
/**
 * Submits the data through the appropiate way. Saves into the filesystem when
 * `online=false` and to the cloud when `online=true`
 * @param isOnline Has the user authenticated through Google OAuth?
 * @param validations All the validated data for a single file
 */
export default async function submitValidations({
  isOnline,
  validations,
}: Props) {
  const validationArray = validationToArray(validations);

  // This validation was left here for future use if we support online submissions
  if (isOnline) {
    console.warn("Online submissions were disabled.");
  } else {
    await offline(validationArray);
  }
}
