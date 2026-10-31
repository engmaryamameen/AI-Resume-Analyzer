import type { SVGProps } from "react";

const paths = {
  grid: "M5 3.75h4.5a1.25 1.25 0 0 1 1.25 1.25v5.5a1.25 1.25 0 0 1-1.25 1.25H5a1.25 1.25 0 0 1-1.25-1.25V5A1.25 1.25 0 0 1 5 3.75Z M14.5 3.75H19A1.25 1.25 0 0 1 20.25 5v2.5A1.25 1.25 0 0 1 19 8.75h-4.5a1.25 1.25 0 0 1-1.25-1.25V5a1.25 1.25 0 0 1 1.25-1.25Z M5 15.25h4.5a1.25 1.25 0 0 1 1.25 1.25V19a1.25 1.25 0 0 1-1.25 1.25H5A1.25 1.25 0 0 1 3.75 19v-2.5A1.25 1.25 0 0 1 5 15.25Z M14.5 12.25H19a1.25 1.25 0 0 1 1.25 1.25V19A1.25 1.25 0 0 1 19 20.25h-4.5A1.25 1.25 0 0 1 13.25 19v-5.5a1.25 1.25 0 0 1 1.25-1.25Z",
  document:
    "M13.5 3.25H6.75a2 2 0 0 0-2 2v13.5a2 2 0 0 0 2 2h10.5a2 2 0 0 0 2-2V9l-5.75-5.75Z M13.25 3.5V9.25H19 M8.25 13h7.5 M8.25 16.75h5",
  briefcase:
    "M8.5 7V5.25a1.5 1.5 0 0 1 1.5-1.5h4a1.5 1.5 0 0 1 1.5 1.5V7 M5.25 7.25h13.5a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5.25a2 2 0 0 1-2-2v-9a2 2 0 0 1 2-2Z M3.5 11.25a23 23 0 0 0 17 0 M10.25 12.75v2h3.5v-2",
  history: "M4.75 7.75A8.25 8.25 0 1 1 3.8 15.25 M3.75 3.75v5h5 M12 7.5v5l3.25 2",
  settings:
    "M19.65 9.66 L21.88 10.44 L21.88 13.56 L19.65 14.34 L19.06 15.76 L20.09 17.88 L17.88 20.09 L15.76 19.06 L14.34 19.65 L13.56 21.88 L10.44 21.88 L9.66 19.65 L8.24 19.06 L6.12 20.09 L3.91 17.88 L4.94 15.76 L4.35 14.34 L2.12 13.56 L2.12 10.44 L4.35 9.66 L4.94 8.24 L3.91 6.12 L6.12 3.91 L8.24 4.94 L9.66 4.35 L10.44 2.12 L13.56 2.12 L14.34 4.35 L15.76 4.94 L17.88 3.91 L20.09 6.12 L19.06 8.24 Z M15.25 12a3.25 3.25 0 1 1-6.5 0 3.25 3.25 0 0 1 6.5 0",
  arrowUpRight: "M7 17L17 7 M7 7h10v10",
  arrowLeft: "M19 12H5 M11 6l-6 6 6 6",
  chevronDown: "M6 9l6 6 6-6",
  menu: "M4 6h16 M4 12h16 M4 18h16",
  minus: "M5 12h14",
  x: "M6 6l12 12 M18 6L6 18",
  help: "M12 17h.01 M9.1 9a3 3 0 1 1 5.8 1c-.6 1-2.9 1.5-2.9 3 M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20",
  list: "M8 6h13 M8 12h13 M8 18h13 M3 6h.01 M3 12h.01 M3 18h.01",
  arrow: "M5 12h14 M13 6l6 6-6 6",
  upload: "M12 16V3 M7 8l5-5 5 5 M4 16v5h16v-5",
  check: "M5 12l4 4L19 6",
  shield: "M12 2l9 4v6c0 5-9 10-9 10S3 17 3 12V6z M8 12l3 3 5-6",
  search: "M21 21l-6-6 M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14",
  plus: "M12 5v14 M5 12h14",
  eye: "M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7 M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6",
  eyeOff:
    "M3 3l18 18 M10.5 5.1L12 5c6.5 0 10 7 10 7a20 20 0 0 1-3.1 3.9 M6.2 6.2A24 24 0 0 0 2 12s3.5 7 10 7c1.8 0 3.3-.5 4.6-1.2 M10 10a3 3 0 0 0 4 4",
  logout: "M9 3H3v18h6 M10 12h11 M16 7l5 5-5 5",
} as const;
export type IconName = keyof typeof paths;
export function Icon({
  name,
  size = 20,
  ...props
}: SVGProps<SVGSVGElement> & { name: IconName; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      className="app-icon"
      {...props}
    >
      <path d={paths[name]} />
    </svg>
  );
}
