import api from "@/services/api";

import z from "zod";
import { useSchemedMutation } from "../utils";

export const useConnectToHost = () => {
  return useSchemedMutation({
    mutationKey: ["healthcheck"],
    mutationFn: (host: string) => {
      const url = new URL(host).toString().replace(/\/$/, "");
      return api.get(`${url}/server/healthcheck`).then((r) => r.data);
    },
    schema: z.object({
      status: z.string(),
    }),
    onSuccess: (_data, host) => {
      api.defaults.baseURL = host;
    },
  });
};
