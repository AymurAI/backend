import z from "zod";

export const healthcheckSchema = z.object({
  status: z.enum(["ok"]),
});
