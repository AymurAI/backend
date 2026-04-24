import type { FormData } from "@/hooks/useForm";
import type { PredictLabel } from "./aymurai";

export interface Paragraph {
  value: string;
  id: string;
  document_id: string;
}

/**
 * Type that defines the properties of a processed file
 */
export type DocFile = {
  /**
   * .docx file contents
   */
  data: File;
  /**
   * File paragraph data and their metadate
   */
  paragraphs?: Paragraph[];
  /**
   * Used on the 'preview' page to detect which files have to be processed
   */
  selected: boolean;
  /**
   * Predictions made by the AI
   */
  predictions?: PredictLabel[];
  /**
   * Is the file validated by the validation form? This is toggled when the user clicks on the 'Validar documento' button
   */
  validated?: boolean;
  /**
   * Data from the form
   */
  validationObject: FormData;
};
