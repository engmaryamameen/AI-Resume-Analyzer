import contracts from "./response-contracts.json";
import * as generated from "./response-validators";

const validators = generated as Record<string, (payload: unknown) => boolean>;
const routes = contracts.routes.map((route, index) => ({
  ...route,
  validate: validators[`response${index}`],
  pattern: new RegExp(`^${route.path.replace(/\{[^}]+\}/g, "[^/]+")}$`),
}));

export function validateResponse(
  path: string,
  method: string,
  status: number,
  payload: unknown,
): boolean {
  const route = routes.find(
    (route) =>
      route.method === method &&
      route.status === status &&
      route.pattern.test(path.split("?")[0] ?? ""),
  );
  return route?.validate?.(payload) === true;
}
