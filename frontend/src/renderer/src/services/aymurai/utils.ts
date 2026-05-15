import { getApiBaseUrl } from "@/services/api";
import axios from "axios";

export const fetcher = axios.create({
  baseURL: getApiBaseUrl(),
});
