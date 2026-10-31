import { cp } from "node:fs/promises";
import { fileURLToPath, pathToFileURL } from "node:url";
import { resolve } from "node:path";

const root = fileURLToPath(new URL("../", import.meta.url));
const standalone = resolve(root, ".next/standalone");
// Standalone output deliberately excludes assets. Keep native startup identical to the Docker image.
await cp(resolve(root, "public"), resolve(standalone, "public"), { recursive: true });
await cp(resolve(root, ".next/static"), resolve(standalone, ".next/static"), { recursive: true });
process.env.HOSTNAME = process.env.LISTEN_HOST ?? "127.0.0.1";
await import(pathToFileURL(resolve(standalone, "server.js")).href);
