import axios from "axios";

const API_PREFIX = "/api";

function trimTrailingSlash(value: string): string {
  return value.replace(/\/$/, "");
}

export function getApiBaseUrl(host: string = window.location.origin): string {
  const origin = trimTrailingSlash(new URL(host).toString());
  if (origin.endsWith(API_PREFIX)) return origin;
  return `${origin}${API_PREFIX}`;
}

export function setApiBaseUrl(host?: string): string {
  const baseURL = getApiBaseUrl(host);
  api.defaults.baseURL = baseURL;
  return baseURL;
}

const api = axios.create({
  baseURL: getApiBaseUrl(),
});

export default api;
