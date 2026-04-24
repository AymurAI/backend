import axios from "axios";

import { AYMURAI_API_URL } from "@/utils/config";

const api = axios.create({
  baseURL: AYMURAI_API_URL,
});

export default api;
